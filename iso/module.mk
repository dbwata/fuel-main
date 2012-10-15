/:=$(BUILD_DIR)/iso/

CENTOS_63_RELEASE:=6.3
CENTOS_63_ARCH:=x86_64
CENTOS_63_MIRROR:=http://mirror.yandex.ru/centos/$(CENTOS_63_RELEASE)/os/$(CENTOS_63_ARCH)
CENTOS_63_GPG:=http://mirror.yandex.ru/centos

.PHONY: iso
all: iso

ISOROOT:=$/isoroot
ISOLINUX_FILES:=boot.msg grub.conf initrd.img isolinux.bin memtest splash.jpg vesamenu.c32 vmlinuz
IMAGES_FILES:=install.img
#IMAGES_FILES:=efiboot.img efidisk.img install.img
GPGFILES:=RPM-GPG-KEY-CentOS-6 RPM-GPG-KEY-CentOS-Debug-6 RPM-GPG-KEY-CentOS-Security-6 RPM-GPG-KEY-CentOS-Testing-6

iso: $/nailgun-centos-6.3-amd64.iso
mirror: $/isoroot-packages.done

$/isoroot-infra.done: 
	mkdir -p $(ISOROOT)
	#scripts/mirror.sh $(GOLDEN_MIRROR) $(LOCAL_MIRROR)
	$(ACTION.TOUCH)

$/isoroot-centos.done: \
		$(BUILD_DIR)/packages/rpm/rpm.done \
		$(centos.packages)/cache.done \
		$(centos.packages)/comps.xml \
		$(ISOROOT)/.discinfo \
		$(ISOROOT)/.treeinfo
	mkdir -p $(ISOROOT)/Packages
	find $(centos.packages)/Packages -name '*.rpm' -exec cp -n {} $(ISOROOT)/Packages \;
	find $(BUILD_DIR)/packages/rpm/RPMS -name '*.rpm' -exec cp -n {} $(ISOROOT)/Packages \;
	createrepo -g `readlink -f "$(centos.packages)/comps.xml"` -u media://`head -1 $(ISOROOT)/.discinfo` $(ISOROOT)
	$(ACTION.TOUCH)

$(ISOROOT)/repodata/comps.xml.gz:
	mkdir -p $(ISOROOT)/repodata
	wget -O $(ISOROOT)/repodata/comps.xml.gz $(CENTOS_63_MIRROR)/`wget -qO- $(CENTOS_63_MIRROR)/repodata/repomd.xml | \
	 xml2 | grep 'comps\.xml\.gz' | awk -F'=' '{ print $$2 }'`

$(centos.packages)/comps.xml: $(ISOROOT)/repodata/comps.xml.gz
	gunzip -c $(ISOROOT)/repodata/comps.xml.gz > $(centos.packages)/comps.xml

$(ISOLINUX_FILES):
	mkdir -p $(ISOROOT)/isolinux/
	test -f $(ISOROOT)/isolinux/$@ || wget -O $(ISOROOT)/isolinux/$@ $(CENTOS_63_MIRROR)/isolinux/$(@F)

$(ISOROOT)/isolinux/isolinux.cfg: iso/isolinux/isolinux.cfg ; $(ACTION.COPY)

$/isoroot-isolinux.done: \
		$(ISOLINUX_FILES) \
		$(ISOROOT)/isolinux/isolinux.cfg \
	$(ACTION.TOUCH)

$(IMAGES_FILES):
	mkdir -p $(ISOROOT)/images/
	test -f $(ISOROOT)/images/$@ || wget -O $(ISOROOT)/images/$@ $(CENTOS_63_MIRROR)/images/$(@F)

$/isoroot-prepare.done:\
		$(IMAGES_FILES) \
	$(ACTION.TOUCH)

$(GPGFILES):
	test -f $(ISOROOT)/$@ || wget -nc -O $(ISOROOT)/$@ $(CENTOS_63_GPG)/$(@F)

$/isoroot-gpg.done:\
		$(GPGFILES) \
	$(ACTION.TOUCH)

$/isoroot.done: \
		$/isoroot-infra.done \
		$/isoroot-centos.done \
		$/isoroot-prepare.done \
		$/isoroot-gpg.done \
		$/isoroot-isolinux.done \
		$(ISOROOT)/ks.cfg \
		$(ISOROOT)/sync \
		$(addprefix $(ISOROOT)/sync/,$(call find-files,iso/sync)) \
#		$(ISOROOT)/EFI \
#		$(addprefix $(ISOROOT)/EFI/,$(call find-files,iso/EFI)) \
		$(addprefix $(ISOROOT)/nailgun/,$(call find-files,nailgun)) \
		$(addprefix $(ISOROOT)/nailgun/bin/,create_release agent) \
		$(addprefix $(ISOROOT)/nailgun/cookbooks/,$(call find-files,cookbooks)) \
		$(addprefix $(ISOROOT)/nailgun/,openstack-essex.json) \
		$(ISOROOT)/eggs \
		$(ISOROOT)/gems/gems \
	$(ACTION.TOUCH)

$(ISOROOT)/sync:
	mkdir -p $@
$(ISOROOT)/sync/%: iso/sync/% ; $(ACTION.COPY)
#$(ISOROOT)/EFI:
#	mkdir -p $@
#$(ISOROOT)/EFI/%: iso/EFI/% ; $(ACTION.COPY)
$(ISOROOT)/ks.cfg: iso/ks.cfg ; $(ACTION.COPY)

$(ISOROOT)/nailgun/openstack-essex.json: scripts/release/openstack-essex.json ; $(ACTION.COPY)
$(ISOROOT)/nailgun/cookbooks/%: cookbooks/% ; $(ACTION.COPY)
$(ISOROOT)/nailgun/bin/%: bin/% ; $(ACTION.COPY)
$(ISOROOT)/nailgun/%: nailgun/% ; $(ACTION.COPY)
$(ISOROOT)/.discinfo: iso/.discinfo ; $(ACTION.COPY)
$(ISOROOT)/.treeinfo: iso/.treeinfo ; $(ACTION.COPY)
$(ISOROOT)/eggs:
	mkdir -p $@
	cp $(LOCAL_MIRROR)/eggs/* $(ISOROOT)/eggs/
$(ISOROOT)/gems/gems:
	mkdir -p $@
	cp $(LOCAL_MIRROR)/gems/* $(ISOROOT)/gems/gems
	gem generate_index -d $(ISOROOT)/gems

$/nailgun-centos-6.3-amd64.iso: $/isoroot.done
	rm -f $@
	mkisofs -r -V "Mirantis Nailgun" -p "Mirantis" \
		-J -T -R -b isolinux/isolinux.bin \
		-no-emul-boot \
		-boot-load-size 8 -boot-info-table \
		-x "lost+found" -o $@ $(ISOROOT)
	implantisomd5 $/nailgun-centos-6.3-amd64.iso
