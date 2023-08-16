# 如何打包

### windows下的可执行文件打包(.exe)
- 使用pyinstaller（https://blog.csdn.net/lojloj/article/details/131760390）
```
pip install Pyinstaller
pyinstaller app.py
```
注意事项：
1.打包生成的exe在dist/app目录下
2.记得把config.json和plugins目录(主要是目录下的plugins.json)也拷贝到dist/app目录下
3.使用命令行运行./app.exe
