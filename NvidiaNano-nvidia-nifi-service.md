# FULL MINIFI CLEAN + REINSTALL + CONTROL DOC
Install path:
    /home/tunastreet/nifi-minifi-cpp-1.26.02/

============================================================
1) UNINSTALL / REMOVE MINIFI COMPLETELY
============================================================

Stop any running agent:
```bash
sudo pkill -9 minifi
```

Remove the systemd service:
```bash
sudo systemctl stop minifi 2>/dev/null
sudo systemctl disable minifi 2>/dev/null
sudo rm -f /usr/local/lib/systemd/system/minifi.service
sudo systemctl daemon-reload
```

Delete the install directory:
```bash
sudo rm -rf /home/tunastreet/nifi-minifi-cpp-1.26.02
```

Delete leftover state/config/cache:
```bash
rm -rf ~/.cache/minifi
rm -rf ~/.config/minifi
rm -rf ~/.local/share/minifi
sudo rm -rf /var/lib/minifi 2>/dev/null
```

============================================================
2) INSTALL THE SERVICE (EFM BOOTSTRAP INSTALL)
============================================================

Assuming MiNiFi is extracted again to:
    /home/tunastreet/nifi-minifi-cpp-1.26.02/

Install the service:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh install
```

This creates:
    /usr/local/lib/systemd/system/minifi.service

============================================================
3) START / STOP / RESTART MINIFI
============================================================

Using minifi.sh (preferred):

Start:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh start
```

Stop:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh stop
```

Restart:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh restart
```

Status:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh status
```

Using systemctl (also works):

Start:
```bash
sudo systemctl start minifi
```

Stop:
```bash
sudo systemctl stop minifi
```

Restart:
```bash
sudo systemctl restart minifi
```

Status:
```bash
systemctl status minifi --no-pager
```

============================================================
4) DISABLE SERVICE AUTO-START AT BOOT
============================================================

Disable autostart:
```bash
sudo systemctl disable minifi
```

Manual start if needed:
```bash
sudo systemctl start minifi
```

Or:
```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh start
```

============================================================
END OF DOCUMENT
============================================================
