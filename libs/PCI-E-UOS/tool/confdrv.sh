#!/bin/bash

#ENABLE_DEBUG=1

rcarch=`arch`

#ukeyvendor=055c
#ukeyproduct=e618

RSPS10_ROOT=$(dirname $(dirname $(readlink -f "$0")))
echo "RSPS10_ROOT:" $RSPS10_ROOT
if [ x"$ENABLE_DEBUG" == x"1" ] ; then
    echo "============================================="
    echo "RSPS10_ROOT:" $RSPS10_ROOT
    echo "============================================="
fi

if [ -n "$BASH_SOURCE" -a "$BASH_SOURCE" != "$0" ]
then
    rootdir=$(dirname $(dirname $(readlink -f "${BASH_SOURCE[0]}")))
    curuser=$(whoami)
    if [ -d $rootdir ] ; then
        echo "=========== SET TSR_ROOT DIR ==========="
        echo "TSR_ROOT:" $rootdir
        echo "TSR_USER:" $curuser
        echo "========================================"

		export TSR_ROOT=$rootdir
		export TSR_USER=$curuser
    else
        echo "dir error"
    fi
else
    echo "DO NOT run this file directly in the shell"
fi

#if  [ "root" = `whoami` -a s"$TSR_USER" != s"" ]; then
    rmmod tsr_drv   2> /dev/null
    rmmod tsrpfdrv  2> /dev/null
    insmod $RSPS10_ROOT/driver/tsr-drv.ko
    sleep 2
    chmod 777 /dev/tsr-dev*

    #export LD_LIBRARY_PATH=
    #export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$RSPS10_ROOT/source/apilib
#    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$RSPS10_ROOT/thirdpart/mtoken_gm3000/lib

    $RSPS10_ROOT/tool/gdacmmktool mr 20f000 | grep "val: 0x00000000"
    if [ $? -eq 0 ] ; then
        echo "================================"
        echo "CONF RPU FIRMWARE for HOST"
        echo "================================"
        #$RSPS10_ROOT/tool/rsptool edev rpucfg name tsr.bin
        $RSPS10_ROOT/tool/mmkstart.out 1
    else
       echo "================================"
       echo "NO CONF RPU FIRMWARE for VF"
       echo "================================"
    fi

    chmod 777 /dev/shm -R

    #ukeybus=`lsusb -d $ukeyvendor:$ukeyproduct | awk -F '[ :]' {'print $2'}`
    #ukeydev=`lsusb -d $ukeyvendor:$ukeyproduct | awk -F '[ :]' {'print $4'}`
#
    #if [ x"$ENABLE_DEBUG" == x"1" ] ; then
    #    echo "/dev/bus/usb/$ukeybus/$ukeydev"
    #fi
#
    #chmod 777 /dev/bus/usb/$ukeybus/$ukeydev
#
    #if [ s"x86_64" = s"$rcarch" ]; then
    #    echo "ukey on arch $rcarch"
    #    cp $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/x64/libgm3000.1.0.so $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/libgm3000.1.0.so
    #elif [ s"mips64" = s"$rcarch" ]; then
    #    echo "ukey on arch $rcarch"
    #    cp $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/mips64/libgm3000.1.0.so $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/libgm3000.1.0.so
    #elif [ s"aarch64" = s"$rcarch" ]; then
    #    echo "ukey on arch $rcarch"
    #    cp $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/ft/libgm3000.1.0.so $RSPS10_ROOT/thirdpart/mtoken_gm3000/lib/libgm3000.1.0.so
    #fi

    #$RSPS10_ROOT/tool/rsptool edev loadkey
    $RSPS10_ROOT/tool/mmkstart.out 2

#else
#    echo "This scripts need ROOT privilege !!!"
#    echo "Using cmd:"
#    echo "  sudo -E ./scripts/confdrv.sh"
#fi

