import re
import os
import uuid
import json
import copy
from oslo_config import cfg
from oslo_i18n._i18n import _
from oslo_log import log as logging
from nova.virt.libvirt import vif as libvirt_vif
from oslo_serialization import jsonutils
from nova.virt.libvirt import utils
from nova.network.neutronv2 import api as neutron_api
from nova import context
from nova.virt.libvirt.freescale import config as fslconfig
from nova.network import model as network_model

LOG = logging.getLogger(__name__)

fsl_sriov_opts = [
            cfg.StrOpt('vendor_id', default="8086"),
            cfg.StrOpt('product_id',default='10ca'),
            cfg.StrOpt('physical_network',default='physnet1'),
            cfg.StrOpt('host', default='sriov-node'),
            cfg.StrOpt('pci_devices', default='/etc/nova/fsl_sriov/pci_devices')
            ]

CONF = cfg.CONF
CONF.register_opts(fsl_sriov_opts, 'fsl_sriov')

HEX_BASE = 16


class FreescaleiNicDriver():

    def __init__(self, get_connection, resources= None):
        #self.libvirt_gen_drv = libvirt_vif.LibvirtGenericVIFDriver(get_connection)
        self.libvirt_gen_drv = libvirt_vif.LibvirtGenericVIFDriver()
        self.resources = jsonutils.loads(resources['pci_passthrough_devices'])
        self.specs = self._prepare_pci_instance_json() 
        utils.write_to_file(CONF.fsl_sriov.pci_devices, jsonutils.dumps(self.specs))
        self.neutron_client = neutron_api.API()
        
        
        
        
           
    def plug(self, instance, vif):
        if CONF.pci_passthrough_whitelist:
            pass
	else:
            self.libvirt_gen_drv.plug(instance, vif)

    def unplug(self, instance, vif):
        vif_type = vif['type']
        if CONF.pci_passthrough_whitelist:
            self._deallocate_pcidevice_for_instance(instance)
        else:
            self.libvirt_gen_drv.unplug(instance, vif)
            

            

    def get_config(self, instance, vif, image_meta,
                   inst_type, virt_type):
        ##Gets an available pci device
        pci_dev = self._is_pci_device_available(instance.uuid)
        if CONF.pci_passthrough_whitelist and pci_dev is not None:
            nw_info = self.neutron_client.get(context.get_admin_context(), vif['network']['id'])
            #vlan_id = unicode(nw_info['provider:segmentation_id'])
  	    vlan_id = unicode(1000)
            mac_addr = unicode(vif['address'])
            conf = self.get_dev_config(mac_addr,vlan_id, pci_dev)
            return conf
        else:
            return self.libvirt_gen_drv.get_config(instance, vif, image_meta,
                        inst_type, virt_type)
    
    def get_dev_config(self, mac_addr, vlan_id, pci_dev):
        conf = None
        conf = fslconfig.FslLibvirtConfigGuestInterface()
        self._set_source_address(conf, pci_dev, vlan_id, mac_addr)

        return conf

    def _str_to_hex(self, str_val):
        ret_val = hex(int(str_val, HEX_BASE))
        return ret_val

    def _set_source_address(self, conf, dev, vlan_id, mac_addr):
        source_address = re.split(r"\.|\:", dev)
        conf.domain, conf.bus, conf.slot, conf.function = source_address
        conf.domain = self._str_to_hex(conf.domain)
        conf.bus = self._str_to_hex(conf.bus)
        conf.slot = self._str_to_hex(conf.slot)
        conf.function = self._str_to_hex(conf.function)
        conf.net_type = 'hostdev'
        conf.mac_addr = mac_addr
        conf.vlan = vlan_id
        
        
    def _prepare_pci_instance_json(self):
        spec = []
        i = 1
        for res in self.resources:
	    pfname = "pf1-vf"+str(i)
            dev = {'dev_id': res['address'], 
                    'instance_uuid': None,
                    'pf_vf_name': pfname}
            spec.append(dev)
            i = i+1
        return spec    


    def _deallocate_pcidevice_for_instance(self, instance):
        """
        Remove the UUID from PCI device spec.
        """
        if CONF.pci_passthrough_whitelist and instance:
           pci_devs = jsonutils.loads(utils.load_file(CONF.fsl_sriov.pci_devices))
           for dev in pci_devs:
               if instance.uuid == dev['instance_uuid']:
                  dev['instance_uuid'] = None
                  pfname = dev['pf_vf_name']
                  intbridge = CONF.neutron.ovs_bridge
		  utils.execute('ovs-vsctl', '--no-wait', 'del-port', intbridge , pfname , run_as_root=True) 
           utils.write_to_file(CONF.fsl_sriov.pci_devices, jsonutils.dumps(pci_devs))

    def _is_pci_device_available(self, instance_uuid):
        pci_devs = jsonutils.loads(utils.load_file(CONF.fsl_sriov.pci_devices))
        assignable_pci_device = None
        for dev in pci_devs:
            if dev['instance_uuid'] is None:
               assignable_pci_device = dev['dev_id']
               dev['instance_uuid'] = instance_uuid
               pfname = dev['pf_vf_name']
               intbridge = CONF.neutron.ovs_bridge
               utils.execute('ovs-vsctl', '--no-wait', 'add-port', intbridge , pfname , '--', 'set', 'interface', pfname, 'type=vf_inic', run_as_root=True)
               break
        utils.write_to_file(CONF.fsl_sriov.pci_devices, jsonutils.dumps(pci_devs))    
        return assignable_pci_device      
    
    
