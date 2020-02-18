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


from gs_ocpmon.platform import Plat
from gs_ocpmon.utils import misc, ExeWrapper



'''
The -health command shows the overall health status of a selected Nytro WarpDrive card and its components. If
any alert exists, this command shows the component causing the alert along with further information. The -health
command Overall Health output possiblities include the following:
 - GOOD. The Nytro WarpDrive card is operating correctly. All operations are supported.
 - WARNING. The Nytro WarpDrive card is approaching failure. This output appears because of a decreased Life
Left value or an increased Temperature value outside the set threshold.
 - ERROR. The Nytro WarpDrive card is not operating. No operations can be performed.
The -health command Life Left output possibilities include percentages between 0 percent and 100 percent.
Zero percent indicates an expired Nytro WarpDrive card warranty.
'''

logger = logging.getLogger("root")


class Msecli(ExeWrapper):
    '''
    classdocs
    '''

    def __init__(self):
        '''
        Constructor
        '''
        super(Msecli, self).__init__("msecli")

        self.alert_map = misc.json_file_to_dict(self.rootdir + "/conf/msecli_alert_map.json")
        self.notify_map = misc.json_file_to_dict(self.rootdir  + "/conf/notify.json")

        self.stash_file = Plat.get_tempdir() + "/ocpmon_msecli-stash.json"
        # baseid for msecli alert, no real significance other than should cont conflict other alert ids
        # Also recieving end might have rules(or workflows) to process these ids.

        self.base_alert_id=6000
        # Temporary use 6000 as Micron SSD alert Base ID

    return_codes = misc.enum(
        NO_CHANGE_IN_HEALTH = 0,
        DIDNT_PASS_THRESHOLD= 1,
        NOT_LOWER_LOW       = 2,
        INFORMATIONAL       = 3,
        WARNING             = 4,
        CRITICAL            = 5,
        UNKNOWN_VALUE       = 6,)

    def get_health(self):

        #cmd_def = self.exe["commands"]["health"]
        result_health = self.runcmd("health")
        result_health = result_health.decode('utf-8')
        # print(result_health)
        result_info = self.runcmd("info")
        result_info = result_info.decode('utf-8')
        # print(result_info)
        output = dict()

        # Est. Life Remaining  : 100%
        lifeleft_re = re.compile(r"""Est\. Life Remaining\s*:\s*(\d+)%$""", re.M)
        output["lifetime_left"] = []
        for i, pctlife in enumerate(re.findall(lifeleft_re, result_health)):
            logger.debug("pct life left [%d]: %s" % (i, pctlife))
            output["lifetime_left"].append(pctlife)

        # Current Temp. (C)    : 40
        ct_re = re.compile(r"""Current Temp\.\s*\(C\)\s*:\s*(\d+)$""", re.M)
        output["drive_temperature"] = []
        for i, ct_status in enumerate(re.findall(ct_re, result_health)):
            logger.debug("current drive temperature [%d]: %s" % (i, ct_status))
            output["drive_temperature"].append(ct_status)

        #Drive Status         : Drive is in good health
        health_re = re.compile(r"""Drive Status\s*:\s*(.+)$""", re.M)
        output["drive_status"] = []
        for i, health_status in enumerate(re.findall(health_re, result_health)):
            logger.info("drive health [%d]: %s" % (i, health_status))
            output["drive_status"].append(health_status)

        # TODO: Implement other information of drives, such as SN, FW, Model etc.
        return output

    def load_stash(self):
        try:
            return misc.json_file_to_dict(self.stash_file)
        except IOError as e:
            logger.info("IOError loading stash file (server was probably rebooted): {0}".format(e))
            # return 100% healthy report as baseline
            logger.info("Defaulting stash to 100% healthy report")
            return self.exe["commands"]["health"]["default_stash"]

    def store_stash(self, stash):
        try:
            misc.dict_to_json_file(stash, self.stash_file)
        except IOError as e:
            logger.critical("IOError saving stash file: {0}".format(e))


    def check_health(self):
        stash = self.load_stash()
        health = self.get_health()
        self.store_stash(health)
        sev = "UNKNOWN"
        sev_was = ""
        sev_now = ""
        direction = "Asserted"
        message = ""

        if health == stash:
            logger.debug("No change in health output detected - exiting")
            return self.return_codes.NO_CHANGE_IN_HEALTH

        for m_name, m_def in self.exe["commands"]["health"]["monitors"].items():
            camel = misc.to_camel_text(m_def["label"])
            # sev = "UNKNOWN"
            # sev_was = ""
            # sev_now = ""
            # direction = "Asserted"
            # message = ""
            # check if we have changes since last stash
            m_was = stash[m_name]
            m_now = health[m_name]
            if m_now == m_was:
                continue

            logger.debug("Change in health output detected. {0} was {1} but is now {2}".format(m_def["label"], m_was, m_now))

            if m_def["type"] == "status":
                for i, (m_now_item, m_was_item) in enumerate(zip(m_now, m_was)):
                    if m_now_item == m_was_item:
                        continue
                    if m_now_item in self.exe["status_value_map"]:
                        sev_now = self.exe["status_value_map"][m_now_item]
                        sev_was = self.exe["status_value_map"][m_was_item]
                        if sev_now == "Informational" or (sev_now == "Warning" and sev_was == "Critical"):
                            direction = "Deasserted"
                        elif sev_now == "Critical" or (sev_now == "Warning" and sev_was == "Informational"):
                            direction = "Asserted"

                        if direction == "Asserted":
                            sev = sev_now
                        else:
                            sev = sev_was

                        message = "Drive #{0}: {1} changed state from {2} to {3}".format(i, m_def["label"], m_was_item, m_now_item)
                        alert_key = "{0}{1} {2}".format(camel, sev, direction)
                        logger.debug("looking up alert id map for {0}".format(alert_key))
                        if alert_key in self.alert_map:
                            alert = self.alert_map[alert_key]
                            message = "{0} {1}".format(camel, message)
                            vars_list = [alert["id"], camel, direction]
                            self.send_alert(message, 5, vars_list)
                        else:
                            logger.critical("failed to find alert_id for [{0}]".format(alert_key))
                            message = "missingAlertIdCritical failed to find alert_id for key {0}".format(alert_key)
                            vars_list = [9999, "missingAlertIdCritical", "Asserted"]
                            self.send_alert(message, 5, vars_list)

                    else:
                        logger.critical("Drive #{0} Unknown value for {1}: {2}".format(i, m_name, m_now_item))
                        message = "Drive #{0} unknownStatusCritical Unknown status value for {1}: {2}".format(i, m_name, m_now_item)
                        vars_list = [9999, "unknownStatusCritical", "Asserted", i]
                        self.send_alert(message, 5, vars_list)
                        # return self.return_codes.UNKNOWN_VALUE

            elif "thresholds" in m_def["type"]:
                thresholds_name = m_def["type"]
                for i, (m_now_item, m_was_item) in enumerate(zip(m_now, m_was)):
                    if m_now_item == m_was_item:
                        continue

                    for sev_key in self.exe[thresholds_name]:
                        if min([int(e) for e in self.exe[thresholds_name][sev_key]]) <= int(m_now_item) <= max([int(e) for e in self.exe[thresholds_name][sev_key]]):
                            sev_now = sev_key
                        if min([int(e) for e in self.exe[thresholds_name][sev_key]]) <= int(m_was_item) <= max([int(e) for e in self.exe[thresholds_name][sev_key]]):
                            sev_was = sev_key

                    if sev_now == sev_was:
                        logger.debug("Drive #{0}: New value for {1} didnt cross a new threshold".format(i, m_def["label"]))
                        continue
                    else:
                        if sev_now == "Informational" or (sev_now == "Warning" and sev_was == "Critical"):
                            direction = "Deasserted"
                        elif sev_now == "Critical" or (sev_now == "Warning" and sev_was == "Informational"):
                            direction = "Asserted"

                    if direction == "Asserted":
                        sev = sev_now
                    else:
                        sev = sev_was

                    logger.debug("Drive #{0}: Crossed threshold for {1} from {2} to {3}, value from {4} to {5}".format(i, m_def["label"], sev_was, sev_now, m_was_item, m_now_item))
                    message = "Drive #{0}: {1} crossed {2} alert threshold from {3} to {4}".format(i, m_def["label"], sev_now, m_was_item, m_now_item)
                    alert_key = "{0}{1} {2}".format(camel, sev, direction)
                    logger.debug("looking up alert id map for {0}".format(alert_key))
                    if alert_key in self.alert_map:
                        alert = self.alert_map[alert_key]
                        message = "{0} {1}".format(camel, message)
                        vars_list = [alert["id"], camel, direction]
                        self.send_alert(message, 5, vars_list)
                    else:
                        logger.critical("failed to find alert_id for [{0}]".format(alert_key))
                        message = "missingAlertIdCritical failed to find alert_id for key {0}".format(alert_key)
                        vars_list = [9999, "missingAlertIdCritical", "Asserted"]
                        self.send_alert(message, 5, vars_list)


    def send_alert(self, message, severity, vars_list=None):
        message = "gs-ocpmon::micron::" + message
        alert_id = vars_list[0]
        logger.warning("sending alert %d: %s" % (alert_id, message))
        for endpoint in self.notify_map["notify"] :
            endpoint = str (endpoint)
            mod = __import__("gs_ocpmon.providers.notifiers."+endpoint.lower(), fromlist=[endpoint])
            klass = getattr(mod,endpoint)
            rc = klass.notify(message, severity,vars_list=vars_list)

            if rc != 0:
                logger.critical("Bad return code from "+ endpoint)

    # TODO: Below function is not working properly. Need to revise it based on msecli_defs.json.
    #       Current the alter map composed by manually. After this function work, it could generate
    #       alter map according the definition table changes.
    def gen_alert_table(self):
        alert_id = self.base_alert_id
        outdict = dict()
        outtsv = ""
        for m_name, m_def in self.exe["commands"]["health"]["monitors"].items():
            camel = misc.to_camel_text(m_def["label"])

            if m_def["type"] == "status":
                things = self.exe["status_value_map"].values()
            else:
                things = self.exe["msecli"]["thresholds"].keys()
            for key in things:
                key = camel + key
                key_a = key + ' Asserted'
                key_d = key + ' Deasserted'
                outdict[key_a] = {"camel": key, "id": alert_id}
                outdict[key_d] = {"camel": key, "id": alert_id + 1}
                outtsv += "{0}\t{1}\t{2}\n".format(alert_id, key, 'assert')
                outtsv += "{0}\t{1}\t{2}\n".format(alert_id+1, key, 'deassert')
                alert_id += 2

        return outdict, outtsv
