# 关于配置：

`config.json`内容如下：

```json
{
    "user_id": "",        
    "total_count": 50,           
    "forum_names": [],
    "BDUSS": "your_BDUSS"             
}
```

$1.$ 配置参数说明

`user_id`：可以输入贴吧id（纯数字）或用户名（注意是用户名不是昵称）；

`total_count`：本次一共查询多少条历史发言；

`forum_names`：按照贴吧名筛选发言，若为空则默认不进行筛选，否则按照如下格式填写可以筛选在对应贴吧的发言：

```json
 "forum_names": ["bangdream","mygo"]
```

`BDUSS`：参考aiotieba官方文档

$2.$ 关于多线程：

考虑到并发过高可能会被ban，最大线程数量设置为了5，每次触发439之后停止若干秒并进行重试，次数为3；