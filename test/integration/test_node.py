import os
import logging
import time
import json
import pprint
import posixpath
from devops.helpers import wait, tcp_ping, http
from integration import ci
from integration.base import Base
from helpers import SSHClient, HTTPClient
from root import root

logging.basicConfig(
    format=':%(lineno)d: %(asctime)s %(message)s',
    level=logging.DEBUG
)

AGENT_PATH = root("bin", "agent")
COOKBOOKS_PATH = root("cooks", "cookbooks")
SAMPLE_PATH = root("scripts", "ci")
SAMPLE_REMOTE_PATH = "/home/ubuntu"
REMOTE_PYTHON = "/opt/nailgun/bin/python"


class StillPendingException(Exception):
    pass


class TestNode(Base):
    def __init__(self, *args, **kwargs):
        super(TestNode, self).__init__(*args, **kwargs)
        self.remote = SSHClient()
        self.client = HTTPClient(
            url="http://%s:8000" % self.get_admin_node_ip()
        )
        self.ssh_user = "root"
        self.ssh_passwd = "r00tme"
        self.admin_host = self.get_admin_node_ip()
        self.remote.connect_ssh(
            self.admin_host,
            self.ssh_user,
            self.ssh_passwd
        )

    def setUp(self):
        pass

    def test_release_upload(self):
        self._upload_sample_release()

    def test_http_returns_200(self):
        resp = self.client.get("/")
        self.assertEquals(200, resp.getcode())

    def test_create_empty_cluster(self):
        self._create_cluster(name='empty')

    def test_node_deploy(self):
        self._bootstrap_slave()

    def test_updating_nodes_in_cluster(self):
        cluster_id = self._create_cluster(name='empty')
        nodes = [str(n['id']) for n in self._bootstrap_slave()]
        self._update_nodes_in_cluster(cluster_id, nodes)

    def test_provisioning(self):
        self._clean_clusters()
        cluster_id = self._create_cluster(name='provision')
        nodes = [str(n['id']) for n in self._bootstrap_slave()]
        self.client.put(
            "/api/nodes/%s/" % nodes[0],
            {"role": "controller", "pending_addition": True}
        )
        self._update_nodes_in_cluster(cluster_id, nodes)
        task = self._launch_provisioning(cluster_id)

        timer = time.time()
        timeout = 1800
        ready = False
        task_id = task['id']
        while not ready:
            task = json.loads(
                self.client.get("/api/tasks/%s" % task_id).read()
            )
            if task['status'] == 'ready':
                logging.info("Installation complete")
                ready = True
            elif task['status'] == 'running':
                if (time.time() - timer) > timeout:
                    raise Exception("Installation timeout expired!")
                time.sleep(30)
            else:
                raise Exception("Installation failed!")
        node = json.loads(self.client.get(
            "/api/nodes/%s/" % nodes[0]
        ).read())
        ctrl_ssh = SSHClient()
        ctrl_ssh.connect_ssh(node['ip'], 'root', 'r00tme')
        ret = ctrl_ssh.execute('test -f /tmp/controller-file')['exit_status']
        self.assertEquals(ret, 0)

        #if node["status"] == "discover":
            #logging.info("Node booted with bootstrap image.")
        #elif node["status"] == "ready":
            #logging.info("Node already installed.")
            #self._slave_delete_test_file()

        #logging.info("Provisioning...")
        #changes = self.client.put(
            #"http://%s:8000/api/clusters/1/changes/" % self.admin_host,
            #log=True
        #)
        #print changes
        #"""
        #task_id = task['task_id']
        #logging.info("Task created: %s" % task_id)
        #"""
        #logging.info(
        #    "Waiting for completion"
        #    " of slave node software installation"
        #)
        #timer = time.time()
        #timeout = 1800
        #while True:
            #try:
                #node = json.loads(self.client.get(
                    #"http://%s:8000/api/nodes/%s" %
                    #(self.admin_host, self.slave_id)
                #))
                #if not node["status"] == 'provisioning':
                    #raise StillPendingException("Installation in progress...")
                #elif node["status"] == 'error':
                    #raise Exception(
                        #"Installation failed!"
                    #)
                #elif node["status"] == 'ready':
                    #logging.info("Installation complete!")
                    #break
            #except StillPendingException:
                #if (time.time() - timer) > timeout:
                    #raise Exception("Installation timeout expired!")
                #time.sleep(30)
        #node = json.loads(self.client.get(
            #"http://%s:8000/api/nodes/%s" % (self.admin_host, self.slave_id)
        #))
        #self.slave_host = node["ip"]
        #logging.info("Waiting for SSH access on %s" % self.slave_host)
        #wait(lambda: tcp_ping(self.slave_host, 22), timeout=1800)
        #self.remote.connect_ssh(
        #    self.slave_host,
        #    self.ssh_user,
        #    self.ssh_passwd
        #)
        ## check if recipes executed
        #ret = self.remote.execute("test -f /tmp/chef_success")
        #if ret['exit_status']:
            #raise Exception("Recipes failed to execute!")
        ## check mysql running
        ##db = MySQLdb.connect(
        #    passwd="test",
        #    user="root",
        #    host=self.slave_host
        #)
        ##print db
        ## chech node status
        #node = json.loads(self.client.get(
            #"http://%s:8000/api/nodes/%s" % (self.admin_host, self.slave_id)
        #))
        #self.assertEqual(node["status"], "ready")
        #self.remote.disconnect()

    def _launch_provisioning(self, cluster_id):
        logging.info(
            "Launching provisioning on cluster %d",
            cluster_id
        )
        changes = self.client.put(
            "/api/clusters/%d/changes/" % cluster_id
        )
        self.assertEquals(200, changes.getcode())
        return json.loads(changes.read())

    def _upload_sample_release(self):
        def _get_release_id():
            releases = json.loads(
                self.client.get("/api/releases/").read()
            )
            for r in releases:
                logging.debug("Found release name: %s" % r["name"])
                if r["name"] == "OpenStack Essex Release":
                    logging.debug("Sample release id: %s" % r["id"])
                    return r["id"]

        release_id = _get_release_id()
        if not release_id:
            raise "Not implemented uploading of release"
        if not release_id:
            raise Exception("Could not get release id.")
        return release_id

    def _create_cluster(self, name='default', release_id=None):
        if not release_id:
            release_id = self._upload_sample_release()

        def _get_cluster_id(name):
            clusters = json.loads(
                self.client.get("/api/clusters/").read()
            )
            for cl in clusters:
                logging.debug("Found cluster name: %s" % cl["name"])
                if cl["name"] == name:
                    logging.debug("Cluster id: %s" % cl["id"])
                    return cl["id"]

        cluster_id = _get_cluster_id(name)
        if not cluster_id:
            resp = self.client.post(
                "/api/clusters",
                data={"name": name, "release": str(release_id)}
            )
            self.assertEquals(201, resp.getcode())
            cluster_id = _get_cluster_id(name)
        if not cluster_id:
            raise Exception("Could not get cluster '%s'" % name)
        return cluster_id

    def _clean_clusters(self):
        clusters = json.loads(self.client.get(
            "/api/clusters/"
        ).read())
        for cluster in clusters:
            resp = self.client.put(
                "/api/clusters/%s" % cluster["id"],
                data={"nodes": []}
            ).read()

    def _update_nodes_in_cluster(self, cluster_id, nodes):
        resp = self.client.put(
            "/api/clusters/%s" % cluster_id,
            data={"nodes": nodes})
        self.assertEquals(200, resp.getcode())
        cluster = json.loads(self.client.get(
            "/api/clusters/%s" % cluster_id).read())
        nodes_in_cluster = [str(n['id']) for n in cluster['nodes']]
        self.assertEquals(nodes, nodes_in_cluster)

    def _bootstrap_slave(self):
        """This function returns list of found nodes
        """
        try:
            self.get_slave_id()
        except:
            pass
        timer = time.time()
        timeout = 600

        slave = ci.environment.node['slave']
        logging.info("Starting slave node")
        slave.start()

        def _get_slave_nodes():
            response = self.client.get("/api/nodes/")
            nodes = json.loads(response.read())
            if nodes:
                return nodes

        while True:
            nodes = _get_slave_nodes()
            if nodes is not None:
                logging.info("Node(s) found")
                break
            else:
                logging.info("Node not found")
                if (time.time() - timer) > timeout:
                    raise Exception("Slave node agent failed to execute!")
                time.sleep(15)
                logging.info("Waiting for slave agent to run...")
        return nodes
