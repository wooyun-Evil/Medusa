#!/usr/bin/env python
# -*- coding: utf-8 -*-
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.header import Header
import base64
import shutil
from config import third_party_mail_host,third_party_mail_user,third_party_mail_pass,local_mail_host,local_mail_user
from Web.DatabaseHub import UserInfo,MaliciousEmail
from django.http import JsonResponse
from ClassCongregation import ErrorLog,GetMailUploadFilePath,GetTempFilePath
import json
from Web.celery import app
from Web.Workbench.LogRelated import UserOperationLogRecord,RequestLogRecord
"""
<p><img src="cid:dns_config"></p>
"""


@app.task
def SendMail(MailMessage,Attachment,Image,MailTitle,Sender,GoalMailbox,ThirdParty,ForgedAddress):
    MailStatus = {}
    # 邮件内容
    TempFilePath = GetTempFilePath().Result()
    MailUploadFilePath = GetMailUploadFilePath().Result()  # 本地文件路径
    for Target in list(set(GoalMailbox)):  # 先去重，然后像多个目标发送
        try:
            EmailBox = MIMEMultipart()  # 创建容器

            EmailBox['From'] = Header(Sender + "<" + ForgedAddress + ">", 'utf-8') # 发送人
            EmailBox['To'] = Header(Target, 'utf-8')# 发给谁
            EmailBox['Subject'] = Header(MailTitle, 'utf-8')  # 标题
            EmailBox["Accept-Language"] = "zh-CN"
            EmailBox["Accept-Charset"] = "ISO-8859-1,utf-8"
            # 消息正文
            TextMessage = MIMEMultipart('alternative')
            EmailBox.attach(TextMessage)
            TextMessage.attach(MIMEText(MailMessage, 'html', 'utf-8'))
            # 发送附件
            for i in Attachment:
                AttachmentTemp = TempFilePath + i  # 文件名字
                AttachmentName = MailUploadFilePath + Attachment[i]  # 文件真实名字
                shutil.copy(AttachmentName, AttachmentTemp)  # 复制到temp目录
                AttachmentData = MIMEApplication(open(AttachmentTemp, 'rb').read())  # 使用temp文件的重命名文件进行发送
                AttachmentData.add_header('Content-Disposition', 'attachment', filename=i)
                TextMessage.attach(AttachmentData)
            # 正文图片
            for x in Image:
                ImageTemp = TempFilePath + x  # 文件名字
                ImageName = MailUploadFilePath + Image[x]  # 文件真实名字
                shutil.copy(ImageName, ImageTemp)  # 复制到temp目录
                pic = MIMEApplication(open(ImageTemp,'rb').read())
                pic.add_header("Content-Disposition", "attachment", filename=x)
                pic.add_header('Content-ID', '<'+x+'>')
                pic.add_header("X-Attachment-Id", "x")
                TextMessage.attach(pic)
            SMTP = smtplib.SMTP()
            if int(ThirdParty) == 1:  # 判断是否使用自建服务器
                SMTP.connect(third_party_mail_host, 25)  # 25 为 SMTP 端口号
                SMTP.login(third_party_mail_user, third_party_mail_pass)
                SMTP.sendmail(third_party_mail_user, Target, EmailBox.as_string())
            else:
                SMTP.connect(local_mail_host, 25)  # 25 为 SMTP 端口号
                #SMTP.set_debuglevel(True)
                SMTP.sendmail(local_mail_user, Target, EmailBox.as_string())
            MailStatus[Target] = "1"  # 写到状态表中
            SMTP.quit()
            SMTP.close()
        except Exception as e:
            MailStatus[Target] = "0"
            ErrorLog().Write("Mail delivery failed->" + str(Target), e)
    MaliciousEmail().UpdateStatus(mail_status=json.dumps(MailStatus), redis_id=SendMail.request.id)#更新数据库



"""send_user_mail
{

	"token": "xxxx",
	"mail_message":"<p>警戒警戒！莎莎检测到有人入侵！数据以保存喵~</p>",
    "attachment": {"Medusa.txt":"AeId9BrGeELFRudpjb7wG22LidVLlJuGgepkJb3pK7CXZCvmM51628131056"},
    "image":{"Medusa.jpg":"2DvWXQc8ufvWMIrhwV5MxrzZZA2oy2f3b5qj5r6VTzb247nQYP1642744866"}
    "mail_title":"测试邮件",
    "sender":"瓜皮大笨蛋",
    "goal_mailbox":["ascotbe@gmail.com","ascotbe@163.com"],
    "third_party":"0",
    "forged_address":"helpdesk@ascotbe.com"
}
"""
def SendUserMail(request):#发送邮件信息
    RequestLogRecord(request, request_api="send_user_mail")
    if request.method == "POST":
        try:
            Token=json.loads(request.body)["token"]
            Uid = UserInfo().QueryUidWithToken(Token)  # 如果登录成功后就来查询UID
            MailMessage = json.loads(request.body)["mail_message"]  # 文本内容
            Attachment = json.loads(request.body)["attachment"]  # 附件列表
            Image=json.loads(request.body)["image"]  # 获取内容图片
            MailTitle = json.loads(request.body)["mail_title"]  # 邮件标题
            Sender = json.loads(request.body)["sender"]  # 发送人姓名
            GoalMailbox = json.loads(request.body)["goal_mailbox"]  # 目标邮箱
            ThirdParty = json.loads(request.body)["third_party"]  # 判断是否是第三方服务器
            ForgedAddress=json.loads(request.body)["forged_address"]  # 伪造发件人
            if Uid != None:  # 查到了UID
                UserOperationLogRecord(request, request_api="send_user_mail", uid=Uid)  # 查询到了在计入
                SendMailForRedis=SendMail.delay(MailMessage,Attachment,Image,MailTitle,Sender,GoalMailbox,ThirdParty,ForgedAddress)#调用下发任务
                MaliciousEmail().Write(uid=Uid,
                                       mail_message=base64.b64encode(str(MailMessage).encode('utf-8')).decode('utf-8'),
                                       attachment=Attachment,
                                       image=Image,
                                       mail_title=base64.b64encode(str(MailTitle).encode('utf-8')).decode('utf-8'),
                                       sender=base64.b64encode(str(Sender).encode('utf-8')).decode('utf-8'),
                                       forged_address=base64.b64encode(str(ForgedAddress).encode('utf-8')).decode('utf-8'),
                                       redis_id=SendMailForRedis.task_id)
                return JsonResponse({'message': "任务下发成功~", 'code': 200, })
            else:
                return JsonResponse({'message': "小宝贝这是非法查询哦(๑•̀ㅂ•́)و✧", 'code': 403, })
        except Exception as e:
            ErrorLog().Write("Web_Mail_Eamil_SendUserMail(def)", e)
            return JsonResponse({'message': "未知错误(๑•̀ㅂ•́)و✧", 'code': 503, })
    else:
        return JsonResponse({'message': '请使用Post请求', 'code': 500, })

