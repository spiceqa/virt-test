"""
A setup test to perform the preliminary actions that are required for
the rest of the tests.

Actions Currently Performed:
(1) installs dogtail on the client
(2) performs required setup to get dogtail tests to work
(2) puts the dogtail scripts onto the client VM

Requires: the client and guest VMs to be setup.
"""

import logging, os
from os import system, getcwd, chdir
from virttest import utils_misc, utils_spice, aexpect

def install_rpm(session, name, rpm):
    """
    installs dogtail on a VM

    @param session: cmd session of a VM
    @rpm: rpm to be installed
    @name name of the package
    
    """
    logging.info("Installing " + name + " from: " + rpm)
    session.cmd("yum -y localinstall %s" % rpm, timeout = 480)
    if session.cmd_status("rpm -q " + name):
        raise Exception("Failed to install " + name)

def deploy_tests_linux(vm, params):
    """
    Moves the dogtail tests to a vm

    @param vm: a VM
    @param params: dictionary of paramaters
    """

    logging.info("Deploying tests")
    script_location = params.get("test_script_tgt")
    old = getcwd()
    chdir(params.get("test_dir"))
    system("zip -r tests .")
    chdir(old)
    vm.copy_files_to("%s/tests.zip" % params.get("test_dir"), \
                     "/home/test/tests.zip")
    session = vm.wait_for_login(
            timeout = int(params.get("login_timeout", 360)))
    session.cmd("unzip -o /home/test/tests.zip -d " + script_location)
    session.cmd("mkdir -p ~/.gconf/desktop/gnome/interface")
    logging.info("Disabling gconfd")
    session.cmd("gconftool-2 --shutdown")
    logging.info("Enabling accessiblity")
    session.cmd("cp %s/%%gconf.xml ~/.gconf/desktop/gnome/interface/" \
                % params.get("test_script_tgt"))

def setup_gui_linux(vm, params, env):
    """
    Setup the vm for GUI testing, install dogtail & move tests over.

@param vm: a VM
@param params: dictionary of test paramaters
"""
    logging.info("Setting up client for GUI tests")
    session = vm.wait_for_login(
                        username = "root", 
                        password = "123456", 
                        timeout=int(params.get("login_timeout", 360)))
    arch = vm.params.get("vm_arch_name")
    fedoraurl = params.get("fedoraurl")
    wmctrl_64rpm = params.get("wmctrl_64rpm")
    wmctrl_32rpm = params.get("wmctrl_32rpm")
    dogtailrpm = params.get("dogtail_rpm")
    if arch == "x86_64":
        wmctrlrpm = wmctrl_64rpm
    else:
        wmctrlrpm = wmctrl_32rpm
    if session.cmd_status("rpm -q dogtail"):
        install_rpm(session, "dogtail", dogtailrpm)
    if session.cmd_status("rpm -q wmctrl"):
        install_rpm(session, "wmctrl", wmctrlrpm)
    deploy_tests_linux(vm, params)

def setup_loopback_linux(vm, params):
    session = vm.wait_for_login(
                        username = "root", 
                        password = "123456", 
                        timeout=int(params.get("login_timeout", 360)))
    session.cmd("echo modprobe snd-aloop >> /etc/rc.modules")
    session.cmd("echo modprobe snd-pcm-oss >> /etc/rc.modules")
    session.cmd("echo modprobe snd-mixer-oss >> /etc/rc.modules")
    session.cmd("echo modprobe snd-seq-oss >> /etc/rc.modules")
    session.cmd("chmod +x /etc/rc.modules") 
    session.cmd_output(params.get("reboot_command_vm2"))

def setup_vm_linux(test, params, env, vm):
    setup_type = vm.params.get("setup_type", None)
    logging.info("Setup type: %s" % setup_type)
    if vm.params.get("display", None) == "vnc":
        logging.info("Display of VM is VNC; assuming it is client")
        if setup_type == "gui":
            setup_gui_linux(vm, params, env)
        elif setup_type == "audio":
            setup_loopback_linux(vm, params)
        else:
            logging.info("Nothing to setup on client")
    else:
        logging.info("Nothing to setup on guest")
    logging.info("Setup complete")

def setup_vm_windows(test, params, env, vm):
    setup_type = vm.params.get("setup_type", None)
    logging.info("Setup type: %s" % setup_type)

    if vm.params.get("display", None) == "vnc":
        logging.info("Display of VM is VNC; assuming it is client")
        utils_spice.install_rv_win(vm, params.get("rv_installer"), env)
        utils_spice.install_usbclerk_win(vm, params.get("usb_installer"), env)
        return

    if setup_type == "guest_tools":
        logging.info("Installing Windows guest tools")
        session = vm.wait_for_login(
                             timeout = int(params.get("login_timeout", 360)))
        winqxl = params.get("winqxl")
        winvdagent = params.get("winvdagent")
        vioserial = params.get("vioserial")
        pnputil = params.get("pnputil")
        winp7 = params.get("winp7zip")
        guest_script_req = params.get("guest_script_req")
        md5sumwin = params.get("md5sumwin")
        md5sumwin_dir = os.path.join("scripts", md5sumwin)
        guest_sr_dir = os.path.join("scripts", guest_script_req)
        guest_sr_path = utils_misc.get_path(test.virtdir, guest_sr_dir)
        md5sumwin_path = utils_misc.get_path(test.virtdir, md5sumwin_dir)
        winp7_path = os.path.join(test.virtdir, 'deps', winp7)
        winqxlzip = os.path.join(test.virtdir, 'deps', winqxl)
        winvdagentzip = os.path.join(test.virtdir, 'deps', winvdagent)
        vioserialzip = os.path.join(test.virtdir, 'deps', vioserial)
        #copy p7zip to windows and install it silently
        logging.info("Installing 7zip")
        vm.copy_files_to(winp7_path, "C:\\")
        session.cmd_status("start /wait msiexec /i C:\\7z920-x64.msi /qn") 

        #copy over the winqxl, winvdagent, virtio serial 
        vm.copy_files_to(winqxlzip, "C:\\")
        vm.copy_files_to(winvdagentzip, "C:\\")
        vm.copy_files_to(vioserialzip, "C:\\")
        vm.copy_files_to(guest_sr_path, "C:\\")
        vm.copy_files_to(md5sumwin_path, "C:\\")
        
        #extract winvdagent zip and start service if vdservice is not installed
        try:
            output = session.cmd('sc queryex type= service state= all' +
                                 ' | FIND "vdservice"')
        except aexpect.ShellCmdError:
            session.cmd_status('"C:\\Program Files\\7-Zip\\7z.exe" e C:\\wvdagent.zip -oC:\\')
            utils_spice.wait_timeout(2)
            session.cmd_status("C:\\vdservice.exe install")
            #wait for vdservice to come up
            utils_spice.wait_timeout(5)
            logging.info(session.cmd("net start vdservice")) 
            logging.info(session.cmd("chdir"))

        #extract winqxl driver, place drivers in correct location & reboot
        #Note pnputil only works win 7+, need to find a way for win xp
        #Verify if virtio serial is already installed
        output = session.cmd(pnputil + " /e")
        if("System devices" in output):
            logging.info( "Virtio Serial already installed")
        else:
            session.cmd_status('"C:\\Program Files\\7-Zip\\7z.exe" e C:\\vioserial.zip -oC:\\')
            output = session.cmd(pnputil + " -i -a C:\\vioser.inf")
            logging.info("Virtio Serial status: " + output)
            #Make sure virtio install is complete
            utils_spice.wait_timeout(5)
        output = session.cmd(pnputil + " /e")
        if("Display adapters" in output):
            logging.info("QXL already installed")
        else:
            #winqxl
            session.cmd_status('"C:\\Program Files\\7-Zip\\7z.exe" e C:\\wqxl.zip -oC:\\')
            output = session.cmd(pnputil + " -i -a C:\\qxl.inf")
            logging.info( "Win QXL status: " + output )
            #Make sure qxl install is complete
            utils_spice.wait_timeout(5)
        vm.reboot()
         
        logging.info("Installation of Windows guest tools completed")

    logging.info("Setup complete")

def setup_vm(test, params, env, vm):
    if vm.params.get("os_type") == "linux":
        setup_vm_linux(test, params, env, vm)
    elif vm.params.get("os_type") == "windows":
        setup_vm_windows(test, params, env, vm)
    else:
        raise error.TestFail("Unsupported OS.")

def run_rv_setup(test, params, env):
    """
    Setup the VMs for remote-viewer testing

    @param test: QEMU test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    for vm in params.get("vms").split():
        logging.info("Setting up VM: " + vm)
        setup_vm(test, params, env, env.get_vm(vm))
