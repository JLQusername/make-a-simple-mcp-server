# make-a-simple-mcp-server
本项目旨在构建一个本地智能舆情分析系统，通过自然语言处理与多工具写作，实现用户查询意图的自动理解、新闻检索、情绪分析、结构化输出与邮件推送。

## 环境搭建

python 3.12

然后安装对应的依赖，缺少什么安装什么即可

然后要在本地增加一个.env文件，需要去阿里百炼平台申请一个key

```.env

BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL=qwq-plus
DASHSCOPE_API_KEY="你的key"

SERPER_API_KEY="618b99091160938bb51b5968aad7312428bbba76"
SMTP_SERVER=发送邮件服务器
SMTP_PORT=465
EMAIL_USER=你的邮箱
EMAIL_PASS=你的授权码

```

## 运行项目

运行项目，在项目根目录下执行`python client.py`

## 运行结果

运行`client.py`：

![c4337ae2bcbe3bbe31874c071125cde](img\client运行1.png)

![5e499aad66c0f241f6cb7cd204aabe9](img\client运行2.png)

![c26006e04c550bc58806b413f7a2644](img\client运行3.png)

![df953e5433dd6b3c088da845576ced4](img\client运行4.png)

可以看到，对应的文件也被保存了

![ef9bf0a1f695c620fa849a2a5e64911](img\client运行5.png)

![1032ecffeeea0ba0bc7cc7f43fec414](img\ggnews.png)

![cb54508c73bb535659e4b8127424c46](img\sentimel_md.png)

![6be28f621ee010e21532ab30e94615d](img\chat.png)

输入quit就可以结束对话

![66a1453198ccba8a93565cb45e02e71](img\client运行6.png)

