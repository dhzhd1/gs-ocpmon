# (C) Copyright 2020, AMAX Information Technologies, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import re
import socket

from ._platform import Base
from gs_ocpmon.utils import ExeWrapper

logger = logging.getLogger("root")


class SmbiosDump(ExeWrapper):

    def __init__(self):
        super(SmbiosDump, self).__init__("smbiosDump", {
            "name": "smbiosDump",
            "path": "",
            "ld_library_path": "",
            "cmdline": "/bin/smbiosDump",
            "commands": {
                "filter": {
                    "args": "%s",
                    "label": "Get DMI field by filter",
                    "type": "exitcode"
                }
            }
        })

    def get_baseboard_manufacturer(self):
        filter_str = ' | grep -i "Board Info" -A 10 | grep -i "Manufacturer" | awk -F\\" \'{print $2}\''
        return self.runcmd("filter", filter_str)

    def get_baseboard_product_name(self):
        filter_str = ' | grep -i "Board Info" -A 10 | grep -i "Product" | awk -F\\" \'{print $2}\''
        return self.runcmd("filter", filter_str)

    def get_baseboard_version(self):
        filter_str = ' | grep -i "Board Info" -A 10 | grep -i "Version" | awk -F\\" \'{print $2}\''
        return self.runcmd("filter", filter_str)

    def get_chassis_asset_tag(self):
        filter_str = ' | grep -i "Board Info" -A 10 | grep -i "Asset Tag" | awk -F\\" \'{print $2}\''
        return self.runcmd("filter", filter_str)

    def get_chassis_serial_number(self):
        filter_str = ' | grep -i "Chassis Info" -A 10 | grep -i "Serial" | awk -F\\" \'{print $2}\''
        return self.runcmd("filter", filter_str)


class Esx(SmbiosDump, Base):
    # requires root - should raise if not root

    default_snmptrap_port = socket.getservbyname('snmptrap')
    default_snmpd_conf_file = "/etc/snmp/snmpd.conf"
    platform = "ESXi"

    # TODO: Need to revise this function since the ESXi 6.7 doesn't have the snmpd.conf
    def get_system_trapsinks(self, snmpd_conf_file=default_snmpd_conf_file, snmptrap_port=default_snmptrap_port):

        # trapsink trapsink.company.com privateComm 1234
        trapsink_re = re.compile(r"""^trapsink\s+(\S+)\s+([\S+]+)(?:\s+(\d+))?""")

        for line in open(snmpd_conf_file):
            match = trapsink_re.match(line)
            if match:
                if match.group(3):
                    snmptrap_port = int(match.group(3))

                return {
                    "hostname": match.group(1),
                    "community": match.group(2),
                    "port": snmptrap_port
                }

        raise RuntimeError("failed to find trapsink entry in {0}".format(snmpd_conf_file))