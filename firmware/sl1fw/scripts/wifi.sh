#!/bin/bash


# ap/client/off
MODE=$1

# once/always
SCOPE=$2

case "$MODE" in
	"ap")
		systemctl stop wpa_supplicant@wlan0.service || exit 2
		systemctl start captive-portal.target || exit 3
		;;
	"cl")
		systemctl stop captive-portal.target || exit 4
		systemctl start wpa_supplicant@wlan0.service || exit 5
		;;
	"of")
		systemctl stop wpa_supplicant@wlan0.service || exit 6
		systemctl stop captive-portal.target || exit 7
		;;
	*)
		echo "Invalid mode $MODE" || exit 1
		;;
esac

if [ $SCOPE == "al" ] ; then
	case "$MODE" in
		"ap")
			systemctl enable captive-portal.target || exit 8
			systemctl disable wpa_supplicant@wlan0.service || exit 9
			;;
		"cl")
			systemctl enable wpa_supplicant@wlan0.service || exit 10
			systemctl disable captive-portal.target || exit 11
			;;
		"of")
			systemctl disable wpa_supplicant@wlan0.service || exit 12
			systemctl disable captive-portal.target || exit 13
			;;
		*)
			echo "Invalid mode $MODE" || exit 1
			;;
	esac
fi
