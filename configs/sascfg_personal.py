"""Konfiguracja dla saspy"""
SAS_config_names = ['ssh_dev',
                   'ssh_batch_dev',
                   'ssh_uat',
                   'ssh_batch_uat',
                   'ssh_prod',
                   'ssh_batch_prod',
                   'ssh_win_dev',
                   'ssh_win_batch_dev',
                   'ssh_win_uat',
                   'ssh_win_batch_uat',
                   'ssh_win_prod',
                   'ssh_win_batch_prod']

# DEV (UNIX)
ssh_dev     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misdev1',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_batch_dev     = {'saspath' : '/sas/conf/DEV/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misdev1',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

# UAT (UNIX)
ssh_uat     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misuat',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_batch_uat     = {'saspath' : '/sas/conf/UAT/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misuat',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

# PROD (UNIX)
ssh_prod     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misprod',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_batch_prod     = {'saspath' : '/sas/conf/PROD/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : '/usr/bin/ssh',
            'host'       : 'misprod',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

# DEV (Windows)
ssh_win_dev     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : 'ssh',
            'host'       : 'misdev1',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_win_batch_dev     = {'saspath' : '/sas/conf/DEV/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : 'ssh',
            'host'       : 'misdev1',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

# UAT (Windows)
ssh_win_uat     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : 'ssh',
            'host'       : 'misuat',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_win_batch_uat     = {'saspath' : '/sas/conf/UAT/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : 'ssh',
            'host'       : 'misuat',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

# PROD (Windows)
ssh_win_prod     = {'saspath' : '/sas/sas94/SASFoundation/9.4/bin/sas_en',
            'ssh'        : 'ssh',
            'host'       : 'misprod',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }

ssh_win_batch_prod     = {'saspath' : '/sas/conf/PROD/ENGINEAdmin/BatchServer/sasbatch.sh',
            'ssh'        : 'ssh',
            'host'       : 'misprod',
            'user'       : 'misadmin',
            'encoding'   : 'latin2',
            'options'    : ["-fullstimer"]
            }
