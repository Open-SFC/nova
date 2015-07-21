# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Freescale Technologies, Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
    Configuration for Guest Interfaces and Devices to support direct and
    hostdev vNICs on top of Freescale HCA embedded Switch.
"""
from lxml import etree
from oslo_log import log as logging
from nova.virt.libvirt import config

LOG = logging.getLogger(__name__)


class FslLibvirtConfigGuestInterface(config.LibvirtConfigGuestDevice):
    """
    @note: Overrides LibvirtConfigGuestDevice to support hosdev
    PCI device when using SR-IOV Virtual Function assignment.
    """
    def __init__(self, **kwargs):
        #super(FslLibvirtConfigGuestInterface, self).__init__(
        #                    root_name="interface",
        #                                **kwargs)
        super(FslLibvirtConfigGuestInterface, self).__init__(
                            root_name="hostdev",
                                        **kwargs)
        self.domain = None
        self.bus = None
        self.slot = None
        self.function = None
        self.net_type = None
        self.mac_addr = None

    def format_dom(self):
        dev = super(FslLibvirtConfigGuestInterface, self).format_dom()
        dev.set("type", self.net_type)
        if self.net_type == "hostdev":
            # Enable below two lines for hostdev.
            # disable for instance

            dev.set("mode", "subsystem")
            dev.set("type", "pci")

            dev.set("managed", "yes")
        dev.append(etree.Element("mac", address=self.mac_addr))                
        source_elem = etree.Element("source")
        addr_elem = etree.Element("address", type='pci')
        
        addr_elem.set("domain", "%s" % (self.domain))
        addr_elem.set("bus", "%s" % (self.bus))
        addr_elem.set("slot", "%s" % (self.slot))
        addr_elem.set("function", "%s" % (self.function))
        source_elem.append(addr_elem)
        dev.append(source_elem)
        vlan_elem = etree.Element("vlan")
        tag_elem = etree.Element("tag", id=self.vlan)
        vlan_elem.append(tag_elem)
        dev.append(vlan_elem)
        return dev
