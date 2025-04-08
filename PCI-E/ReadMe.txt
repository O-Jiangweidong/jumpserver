1、查看是否正确识别密码卡 lspci -d 1dab:

2、将 configs 里的所有文件拷贝到 /etc 目录下

3、将 lib 中的所有文件拷贝到 /lib64 目录下

4、执行如下命令 ./tool/confdrv.sh

5、安装成功后，./tool/gdacmmktool，对密码卡进行测试