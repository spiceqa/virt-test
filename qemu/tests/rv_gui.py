"""
rv_gui.py - A test to run dogtail gui tests from the client.
The test also does verification of the gui tests.

Requires:
1. rv_setup must be run to have dogtail be installed on the client
2. rv_connect must be run to restart the gdm session.
and have to have both client & remote viewer window available.
"""
from virttest.virt_vm import VMDeadError
import os, logging
from autotest.client.shared import error
from virttest.aexpect import ShellCmdError
from virttest import utils_net, utils_spice
from time import sleep

window_title = "'vm1 (1) - Remote Viewer'"

def getres(vm_session):
    """
Gets the resolution of a VM

@param vm_session: cmd session of a VM
"""

    guest_res_raw = None
    try:
        #vm_session.cmd_output("xrandr -d :0 | grep '*' > /tmp/res")
        #guest_res_raw = vm_session.cmd("cat /tmp/res|awk '{print $1}'")
        guest_res_raw = vm_session.cmd_output("xrandr -d :0 2> /dev/null | grep '*'")
        guest_res = guest_res_raw.split()[0]
    except ShellCmdError:
        raise error.TestFail("Could not get guest resolution, xrandr output:" +
                             " %s" % guest_res_raw)
    except IndexError:
        raise error.TestFail("Could not get guest resolution, xrandr output:" +
                             " %s" % guest_res_raw)
    return guest_res

def getrvgeometry(client_session, host_port, host_ip):
    """
Gets the geometry of the rv_window from the client session

@param client_session: cmd session of the client.
@param host_port: host port where the vms are running
@param host_ip: host ip where the vms are running
"""
    #rv_xinfo_cmd = "xwininfo -name 'spice://%s?port=%s (1) - Remote Viewer'" \
    #               % (host_ip, host_port)
    rv_xinfo_cmd = "xwininfo -name %s" % window_title
    rv_xinfo_cmd += " | grep geometry"
    try:
        rv_res_raw = client_session.cmd(rv_xinfo_cmd)
        rv_res_raw = rv_res_raw.split('+')[0]
        rv_res = rv_res_raw.split()[1]
        #print rv_res_raw
        #print rv_res
    except ShellCmdError:
        raise error.TestFail("Could not get the geometry of the rv window")
    except IndexError:
        raise error.TestFail("Could not get the geometry of the rv window")
    return rv_res

def getrvcorners(client_session, host_port, host_ip):
    """
Gets the coordinates of the 4 corners of the rv window

@param client_session: cmd session of the client.
@param host_port: host port where the vms are running
@param host_ip: host ip where the vms are running
"""
#    rv_xinfo_cmd = "xwininfo -name 'spice://%s?port=%s (1) - Remote Viewer'" \
#                   % (host_ip, host_port)
    rv_xinfo_cmd = "xwininfo -name %s" % window_title
    rv_xinfo_cmd += " | grep Corners"
    try:
        rv_corners_raw = client_session.cmd(rv_xinfo_cmd)
        rv_corners = rv_corners_raw.strip()
        #print rv_res_raw
        #print rv_res
    except ShellCmdError:
        raise error.TestFail("Could not get the geometry of the rv window")
    except IndexError:
        raise error.TestFail("Could not get the geometry of the rv window")
    return rv_corners


def checkgeometryincrease(rv_res, rv_res2, errorstr):
    """
Checks for an increase in resolution or geometry

@param rv_res: original resolution
@param rv_res2: secondary resolution that is greater
@errorstr: user defined error string if the check fails
"""
    #Get the required information
    width1 = int(rv_res.split('x')[0])
    width2 = int(rv_res2.split('x')[0])

    #The second split of - is a workaround because the xwinfo sometimes
    #prints out dashes after the resolution for some reason.
    height1 = int(rv_res.split('x')[1].split('-')[0])
    height2 = int(rv_res2.split('x')[1].split('-')[0])

    #Verify the height of has increased
    if(height2 > height1):
        logging.info("Height check was successful")
    else:
        raise error.TestFail("Checking height: " + errorstr)
    #Verify the width of rv window increased after zooming
    if(width2 > width1):
        logging.info("Width check was successful")
    else:
        raise error.TestFail("Checking width: " + errorstr)

def checkresequal(res1, res2, logmessage):
    """
Checks for an increase in resolution or geometry

@param rv_res1: original resolution
@param rv_res2: secondary resolution that should be equal
@logmessage: user defined error string if the check fails
"""
    #Verify the resolutions are equal
    logging.info(logmessage)
    if res1 == res2:
        pass
    else:
        raise error.TestFail("Resolution of the guest has changed")

def percentchange(percent, init, post, msg):
    """
Return the filename corresponding to a given monitor name.

@param percent: Acceptable percent change of x2 from x1.
@param init: original integer value
@param post: integer that must be within an acceptable percent of x1
@msg: String to explain the comparison.
"""
    if not isinstance(init, int):
        init = int(init)
    if not isinstance(post, int):
        post = int(post)
    if not isinstance(percent, int):
        percent = int(percent)


    sub = init*percent/100
    lowerlimit = init - sub
    upperlimit = init + sub
    if (int(init) - sub <= int(post) and int(post) <= (int(init) + sub)):
        logging.info(msg + str(post) + " is within a valid limit " + \
                     str(lowerlimit) + " and " + str(upperlimit))
    else:
        errorstr = "Error:" + msg + str(post) + " is outside the " + \
                    "valid limit " + str(lowerlimit) + " and " + str(upperlimit)
        raise error.TestFail(errorstr)


def run_rv_gui(test, params, env):
    """
Tests GUI automation of remote-viewer

@param test: QEMU test object.
@param params: Dictionary with the test parameters.
@param env: Dictionary with test environment.
"""

    #Get required paramters
    host_ip = utils_net.get_host_ip_address(params)
    screenshot_dir = params.get("screenshot_dir")
    #screenshot_name = params.get("screenshot_name")
    screenshot_exp_name = params.get("screenshot_expected_name")
    expected_rv_corners_fs = "Corners:  +0+0  -0+0  -0-0  +0-0"
    screenshot_exp_file = ""
    host_port = None
    guest_res = ""
    guest_res2 = ""
    rv_res = ""
    rv_res2 = ""
    rv_binary = params.get("rv_binary", "remote-viewer")
    changex = params.get("changex")
    changey = params.get("changey")
    accept_pct = params.get("accept_pct")
    tests = params.get("rv_gui_test_list").split()
    rv_version = params.get("rv_version")
    rv_version_el7 = params.get("rv_version_el7")
    ticket = params.get("spice_password", None)
    errors = 0

    guest_vm = env.get_vm(params["guest_vm"])
    guest_vm.verify_alive()
    guest_session = guest_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))
    guest_root_session = guest_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)),
            username="root", password="123456")


    #update host_port
    host_port = guest_vm.get_spice_var("spice_port")

    client_vm = env.get_vm(params["client_vm"])
    client_vm.verify_alive()
    client_session = client_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    output = client_session.cmd('cat /etc/redhat-release')
    isRHEL7 = "release 7." in output

    client_session.cmd("export DISPLAY=:0")
    guest_session.cmd("export DISPLAY=:0")
    #if isRHEL7:
    # pass
    # client_session.cmd('mkdir /home/test/.dbus/session-bus/
    # client_session.cmd('. /home/test/.dbus/session-bus/`cat ' + \
    # '/etc/machine-id`-0')
    #else:
    client_session.cmd('. /home/test/.dbus/session-bus/`cat ' + \
                       '/var/lib/dbus/machine-id`-0')
    client_session.cmd('export DBUS_SESSION_BUS_ADDRESS ' + \
                       'DBUS_SESSION_BUS_PID DBUS_SESSION_BUS_WINDOWID')


    client_session.cmd("cd %s" % params.get("test_script_tgt"))
    rv_res_orig = getrvgeometry(client_session, host_port, host_ip)
    logging.info("Executing gui tests: " + str(tests))

    #Make sure Accessibility is enabled before running the GUI tests
    if isRHEL7:
        logging.info("Enabling accessibility")
        client_session.cmd("export DISPLAY=:0.0")
        client_session.cmd("gsettings set org.gnome.desktop.interface"
                           " toolkit-accessibility true")

    #Go through all tests to be run
    for i in tests:
        logging.info("Test: " + i)

        #Verification that needs to be done prior to running the gui test.
        if "zoom" in i or "autoresize" in i:
            #Get preliminary information needed for the zoom tests
            guest_res = getres(guest_session)
            rv_res = getrvgeometry(client_session, host_port, host_ip)

        # if i in ("screenshot"):
        if "screenshot" in i:
            screenshot_exp_file = os.path.join(screenshot_dir, \
                                               screenshot_exp_name)
            try:
                client_session.cmd('[ -e ' + screenshot_exp_file +' ]')
                client_session.cmd('rm ' + screenshot_exp_file)
                logging.info("Deleted: " + screenshot_exp_file)
            except ShellCmdError:
                logging.info(screenshot_exp_name + " doesn't exist, continue")

        cmd = "./unittests/%s_rv.py" % i

        #Verification of the printscreen test prior to the test being run
        if "printscreen" in i:
            output = client_session.cmd('cat /etc/redhat-release')
            if "release 7." in output:
                output = guest_session.cmd('rm -vf /home/test/Pictures/Screen*')
                logging.info("Screenshots removed: " + output)

        #Adding parameters to the test
        if (i == "connect"):
            cmd += " 'spice://%s:%s'" % (host_ip, host_port)
            if ticket:
                cmd += " %s > /dev/null 2>&1" % ticket

        #Run the test
        client_session_dt = client_vm.wait_for_login(
                                 timeout=int(params.get("login_timeout", 360)))
        client_session_dt.cmd("export DISPLAY=:0.0") 
        client_session_dt.cmd('. /home/test/.dbus/session-bus/`cat ' + \
                              '/var/lib/dbus/machine-id`-0')
        client_session_dt.cmd('export DBUS_SESSION_BUS_ADDRESS ' + \
                              'DBUS_SESSION_BUS_PID DBUS_SESSION_BUS_WINDOWID')
        print "Running test: " + cmd
        try:
            logging.info(client_session_dt.cmd(cmd))
        except:
            logging.error("Status: FAIL")
            errors += 1
        else:
            logging.info("Status: PASS")
            client_session_dt.close()

        #Wait before doing any verification
        utils_spice.wait_timeout(5)

        #Verification Needed after the gui test was run
        if "zoom" in i:
            guest_res2 = getres(guest_session)
            rv_res2 = getrvgeometry(client_session, host_port, host_ip)
            #Check to see that the resolution doesn't change
            logstr = "Checking that the guest's resolution doesn't change"
            checkresequal(guest_res, guest_res2, logstr)
            if "zoomin" in i:
                #verify the rv window has increased
                errorstr = "Checking the rv window's size has increased"
                logging.info(errorstr)
                checkgeometryincrease(rv_res, rv_res2, errorstr)
            if "zoomout" in i:
                #verify the rv window has decreased
                errorstr = "Checking the rv window's size has decreased"
                logging.info(errorstr)
                checkgeometryincrease(rv_res2, rv_res, errorstr)
            if "zoomnorm" in i:
                errorstr = "Checking the rv window's size is the same as " + \
                           "it was originally when rv was started."
                checkresequal(rv_res2, rv_res_orig, errorstr)

        if "quit" in i or "close" in i:
            #Verify for quit tests that remote viewer is not running on client
            try:
                rvpid = str(client_session.cmd("pgrep remote-viewer"))
                raise error.TestFail("Remote-viewer is still running: " + rvpid)
            except ShellCmdError:
                logging.info("Remote-viewer process is no longer running.")
        if "screenshot" in i:
            #Verify the screenshot was created and clean up
            try:
                client_session.cmd('[ -e ' + screenshot_exp_file + ' ]')
                client_session.cmd('rm ' + screenshot_exp_file)
                print screenshot_exp_name + " was created as expected"
            except ShellCmdError:
                raise error.TestFail("Screenshot " + screenshot_exp_file + \
                                     " was not created")
        if i == "fullscreen" or i == "fullscreen_shortcut":
            #Verify that client's res = guests's res
            guest_res = getres(guest_session)
            client_res = getres(client_session)
            rv_geometry = getrvgeometry(client_session, host_port, host_ip)
            rv_corners = getrvcorners(client_session, host_port, host_ip)
            if(client_res == guest_res):
                logging.info("PASS: Guest resolution is the same as the client")
                #Verification #2, client's res = rv's geometry
                if(client_res == rv_geometry):
                    logging.info("PASS client's res = geometry of rv window")
                else:
                    raise error.TestFail("Client resolution: " + client_res + \
                            " differs from the rv's geometry: " + rv_geometry)

            else:
                raise error.TestFail("Guest resolution: " + guest_res + \
                      "differs from the client: " + client_res)
            #Verification #3, verify the rv window is at the top corner
            if(rv_corners in expected_rv_corners_fs):
                logging.info("PASS: rv window is at the top corner: " + \
                             rv_corners)
            else:
                raise error.TestFail("rv window is not at the top corner " + \
                                     "as expected, it is at: " + rv_corners)
        #Verify rv window < client's res
        if i == "leave_fullscreen" or i == "leave_fullscreen_shortcut":
            rv_corners = getrvcorners(client_session, host_port, host_ip)
            if(rv_corners not in expected_rv_corners_fs):
                logging.info("PASS: rv window is not at top corner: " + \
                             rv_corners)
            else:
                raise error.TestFail("rv window, leaving full screen failed.")

        if "printscreen" in i:
            output = client_session.cmd('cat /etc/redhat-release')
            if "release 7." in output:
                output = guest_session.cmd('ls -al /home/test/Pictures | grep Screen*')
                logging.info("Screenshot Taken Found: " + output)
            else:
                output = guest_root_session.cmd("ps aux | grep gnome-screenshot")
                index = 1
                found = 0
                plist = output.splitlines()
                for line in plist:
                    print str(index) + " " + line
                    index += 1
                    list2 = line.split()
                    #get gnome-screenshot info
                    gss_pid = str(list2[1])
                    gss_process_name = str(list2[10])
                    #Verify gnome-screenshot is running and kill it
                    if gss_process_name == "gnome-screenshot":
                        found = 1
                        guest_root_session.cmd("kill " + gss_pid)
                        break
                    else:
                        continue
                if not (found):
                    raise error.TestFail("gnome-screenshot is not running.")

        #Verify the shutdown dialog is present
        if "ctrl_alt_del" in i:
            #looking for a blank named dialog will not work for RHEL 7
            #Will need to find a better solution to verify
            #the shutdown dialog has come up
            if isRHEL7:
                #wait 80 seconds for the VM to completely shutdown
                utils_spice.wait_timeout(90)
                try:
                    guest_vm.verify_alive()
                    raise error.TestFail("Guest VM is still alive, shutdown failed.")
                except VMDeadError:
                    logging.info("Guest VM is verified to be shutdown")
            else:
                guest_session.cmd("xwininfo -name ''")

        #If autoresize_on is run, change window geometry
        if i == "autoresize_on" or i == "autoresize_off":
            logging.info("Attempting to change the window size of rv to:" + \
                         str(changex) + "x" + str(changey))
            #wmctrl_cmd = "wmctrl -r 'spice://%s?port=%s (1) - Remote Viewer'" \
            #       % (host_ip, host_port)
            wmctrl_cmd = "wmctrl -r %s" % window_title
            wmctrl_cmd += " -e 0,0,0," + str(changex) + "," + str(changey)
            output = client_session.cmd(wmctrl_cmd)
            logging.info("Original res: " + guest_res)
            logging.info("Original geometry: " + rv_res)

            #Wait for the rv window to change and guest to adjust resolution
            utils_spice.wait_timeout(2)

            guest_res2 = getres(guest_session)
            rv_res2 = getrvgeometry(client_session, host_port, host_ip)
            logging.info("After test res: " + guest_res2)
            logging.info("After test geometry: " + rv_res2)

            #Get the required information
            width2 = int(guest_res2.split('x')[0])
            rvwidth2 = int(rv_res2.split('x')[0])

            #The second split of - is a workaround because the xwinfo sometimes
            #prints out dashes after the resolution for some reason.
            height2 = int(guest_res2.split('x')[1].split('-')[0])
            rvheight2 = int(rv_res2.split('x')[1].split('-')[0])

            #the width and height that was specified is changed w/alotted limit
            percentchange(accept_pct, changey, rvheight2, "Height parameter:")
            percentchange(accept_pct, changex, rvwidth2, "Width parameter:")

            if i == "autoresize_on":
                #resolution is changed, attempted to match the window
                logging.info("Checking resolution is changed, attempted" + \
                             " to match the window, when autoresize is on")
                percentchange(accept_pct, rvheight2, height2, "Height param:")
                percentchange(accept_pct, rvwidth2, width2, "Width param:")
            if i == "autoresize_off":
                #resolutions did not change
                logging.info("Checking the resolution does not change" + \
                             ", when autoresize is off")
                logstr = "Checking that the guest's resolution doesn't change"
                checkresequal(guest_res, guest_res2, logstr)

        #Verify a connection is established
        if i == "connect":
            try:
                utils_spice.verify_established(client_vm, host_ip, \
                                               host_port, rv_binary)
            except utils_spice.RVConnectError:
                raise error.TestFail("remote-viewer connection failed")

    if errors:
        raise error.TestFail("%d GUI tests failed, see log for more details" \
                             % errors)
