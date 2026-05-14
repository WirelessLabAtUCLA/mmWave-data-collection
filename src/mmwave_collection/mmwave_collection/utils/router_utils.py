from typing import Any, Dict


def prepare_collection_script(config: Dict[str, Any]) -> str:
    """Single-MAC CSI script (one TX per invocation)."""
    script_content = f'''
        #!/bin/sh
        # CSI Batch Collection Script - {config['measurements_per_batch']} measurements

        echo "[CSI] Starting batch collection..."

        # Empty the data file
        echo "" > {config['remote_file']}

        # Reset the interface
        ip link set dev wlan0 down
        ip link set dev wlan0 up

        # Reset the supplicant
        killall wpa_supplicant

        # Connect
        wpa_supplicant -D nl80211 -i wlan0 -c /etc/wpa_supplicant.conf -B

        # Wait for connection
        i=0
        connected=0

        while true ; do
            connected=$(cat /sys/kernel/debug/ieee80211/phy0/wil6210/stations | grep connected | wc -l)
            
            if [[ $connected -eq 1 ]]; then
                break
            fi
            
            i=$((i+1))
            
            if [[ $i -eq {config['connection_timeout']} ]]; then
                echo "[CSI] Cannot connect after {config['connection_timeout']} seconds"
                echo "Unreachable" > {config['remote_file']}
                exit 1
            fi
            
            sleep 1
        done

        echo "[CSI] Connected, collecting {config['measurements_per_batch']} measurements..."

        # Measurement loop - fixed number
        i=0

        while [ $i -lt {config['measurements_per_batch']} ] ; do
            # Get CSI measurement
            echo -n -e '{config['mac_address']}' | iw dev wlan0 vendor recv 0x001374 0x93 -
            
            # Save the measurement
            echo $(dmesg | tail -n1) >> {config['remote_file']}
            
            i=$((i+1))
        done

        echo "[CSI] Batch complete: $i measurements"
        exit 0
        '''

    return script_content


def prepare_ftm_collection_script(config: Dict[str, Any]) -> str:
    """Single-MAC FTM script (one TX per invocation)."""
    script_content = f'''
        #!/bin/sh
        # FTM Batch Collection Script - {config['measurements_per_batch']} measurements

        echo "[FTM] Starting batch collection..."

        # Empty the data file
        echo "" > {config['remote_file']}

        # Reset the interface
        ip link set dev wlan0 down
        ip link set dev wlan0 up

        # Reset the supplicant
        killall wpa_supplicant

        # Connect
        wpa_supplicant -D nl80211 -i wlan0 -c /etc/wpa_supplicant.conf -B

        # Wait for connection
        i=0
        connected=0

        while true ; do
            connected=$(cat /sys/kernel/debug/ieee80211/phy0/wil6210/stations | grep connected | wc -l)
            
            if [[ $connected -eq 1 ]]; then
                break
            fi
            
            i=$((i+1))
            
            if [[ $i -eq {config['connection_timeout']} ]]; then
                echo "[FTM] Cannot connect after {config['connection_timeout']} seconds"
                echo "Unreachable" > {config['remote_file']}
                exit 1
            fi
            
            sleep 1
        done

        echo "[FTM] Connected, collecting {config['measurements_per_batch']} measurements..."

        # Clear dmesg before starting measurements
        dmesg -c > /dev/null 2>&1

        # Measurement loop - fixed number
        i=0

        while [ $i -lt {config['measurements_per_batch']} ] ; do
            # Get FTM measurement (ToF command)
            echo -n -e '{config['mac_address']}' | iw dev wlan0 vendor recv 0x001374 0x81 -
            
            # Save the measurement
            echo $(dmesg | tail -n1) >> {config['remote_file']}
            
            i=$((i+1))
        done

        echo "[FTM] Batch complete: $i measurements"
        exit 0
        '''

    return script_content
