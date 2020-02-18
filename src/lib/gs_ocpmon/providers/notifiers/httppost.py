# (C) Copyright 2016, Goldman Sachs. All rights reserved.
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
import shlex
import socket
import os
import sys
import subprocess as sub
import urllib
from urllib import request

from gs_ocpmon.platform import Plat
from gs_ocpmon.utils import misc

logger = logging.getLogger("root")


class HTTPPost(object):
    @staticmethod
    def load_config(configFile):
        try:
            return misc.json_file_to_dict(configFile)
        except IOError as e:
            logger.info("IOError loading Config file : {0}".format(e))
            print("IOError loading Config File")

    @classmethod
    def notify (cls,message, severity, alertgroup=None,alerttype='http',installer=None,category=None, platform='UNIX', division=None, bu=None, vars_list=None):
        '''
        -s severity (0=test/temp,1=auto, 2=ops(warn), 3=ops(minor), 4=ops(major),5=ops(critical)
        '''
        root_module = sys.modules[cls.__module__.split('.')[0]].__file__
        rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(root_module))))
        config_file = rootdir+"/conf/notify.json"

        if os.path.exists(config_file):
            config_dict = cls.load_config(config_file)
            try:
                post_uri = config_dict['notification_endpoints'][cls.__name__]['url']
            except KeyError:
                logger.info("There is no \"url\" key in the config file")
                raise RuntimeError( "No configured HTTPPost-URL ")
        else :
            raise RuntimeError( "No configured HTTPPost-URL ")
        host = socket.gethostname()
        _plat = Plat()
        platform = _plat.platform
        if vars_list:
            vars_str = ','.join(str(x) for x in vars_list)
        status_alert_dict_original = {}
        status_alert_dict_original.update({'message' : message ,'division' : division , 'bu' :bu ,'severity' : severity ,'alertgroup': alertgroup ,'installer' : installer ,'category': category ,'platform':platform,'host': host,'alerttype' :alerttype, 'varslist' : vars_str })
        status_alert_dict =  dict((k, v) for k, v in status_alert_dict_original.items() if v is not None)
        status_alert_json = misc.dict_to_json(status_alert_dict)
        print(status_alert_json)
        req = urllib.request.Request(post_uri,status_alert_json.encode("utf-8"),{'Content-Type': 'application/json'})
        print(req)
        response = urllib.request.urlopen(req)
        rc = response.getcode()
        print(rc)
        logger.info("Http-Post returncode = {0}".format(rc))

        # Below condiftion should be adjusted by the actually web service design.
        if rc != 200:
            # logger.critical("Http-Post failed:\n\tcommand: {0}\n\treturn code:{1}\n\tstderr: {2}".format(command, rc, cmd_err))
            logger.critical("Http-Post failed:\n\tcommand: {0}\n\treturn code:{1}\n\tstderr: {2}".format("failed-command-from-webservice", rc, "failed-information-passed-from-webservice"))
            return 1
        else:
            return 0
