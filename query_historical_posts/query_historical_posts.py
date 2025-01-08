import asyncio
import aiotieba as tb
import datetime
import pytz
import json
import aiofiles
import time
import re
import random

# 定义本地时区（Asia/Shanghai）
local_tz = pytz.timezone('Asia/Shanghai')

# 转换 UNIX 时间戳为本地时间格式
def convert_to_local_time(timestamp):
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    dt_utc = pytz.utc.localize(dt)
    dt_local = dt_utc.astimezone(local_tz)
    return dt_local.strftime('%Y-%m-%d %H:%M:%S')

# 生成文件名：根据 user_id 和 forum_names 动态生成
def generate_output_filename(user_id, forum_names, output_type="posts"):
    # 如果 forum_names 非空，将其用下划线连接
    if forum_names:
        forum_part = '_'.join(forum_names)
    else:
        forum_part = "all_forums"  # 如果 forum_names 为空，使用默认名称

    # 使用正则去掉文件名中的特殊字符（如中文字符可能带来的问题）
    safe_user_id = re.sub(r'[^a-zA-Z0-9_]', '_', user_id)  # 替换掉不安全的字符
    safe_forum_part = re.sub(r'[^a-zA-Z09_]', '_', forum_part)  # 替换掉不安全的字符

    # 组合成文件名，并加上 .json 后缀
    output_filename = f"{safe_user_id}_{safe_forum_part}_{output_type}.json"
    return output_filename

# 定义一个限流的信号量，最多允许 5 个并发线程
semaphore = asyncio.Semaphore(5)

# 获取关注的吧
async def fetch_followed_forums(client, id_, retry_count=3):
    follow_forums = []  # 用于保存关注的贴吧信息

    attempt = 0
    while attempt < retry_count:
        try:
            # 获取关注的贴吧（每次最多返回50个）
            result = await client.get_follow_forums(id_, pn=1, rn=50)
            
            for forum in result.objs:
                forum_data = {
                    "fid": forum.fid,
                    "fname": forum.fname,
                    "level": forum.level,
                    "exp": forum.exp
                }
                follow_forums.append(forum_data)

            break
        except Exception as e:
            print(f"获取关注的贴吧失败，尝试第 {attempt + 1} 次重试：{e}")
            attempt += 1
            if attempt < retry_count:
                wait_time = random.uniform(3, 5)  # 随机等待 3 到 5 秒
                print(f"等待 {wait_time:.2f} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                print("重试次数达到上限，跳过该请求")
    return follow_forums

# 获取帖子
async def fetch_page_posts(client, id_, forum_names, forum_ids, page, page_size, retry_count=3):
    page_posts = []  # 用于保存当前页的数据

    async with semaphore:
        attempt = 0
        while attempt < retry_count:
            try:
                user_posts = await client.get_user_posts(id_=id_, pn=page, rn=page_size)
                
                if not user_posts.objs:
                    return page_posts  # 返回空列表表示当前页面没有数据

                for user_post in user_posts.objs:
                    for post in user_post.objs:
                        if not forum_ids or post.fid in forum_ids:
                            content = ''.join([frag.text for frag in post.contents.objs]) if post.is_comment else post.contents.objs[0].text
                            user_name = post.user.user_name
                            create_time = post.create_time
                            if forum_ids:
                                forum_name = [fname for fname, fid in zip(forum_names, forum_ids) if fid == post.fid][0]
                            else:
                                forum_detail = await client.get_forum_detail(post.fid)
                                forum_name = forum_detail.fname if forum_detail else "未知"
                            tid = post.tid
                            local_time = convert_to_local_time(create_time)
                            post_tid = await client.get_posts(int(tid))

                            # 将当前帖子内容添加到列表中
                            page_posts.append({
                                "forum_name": forum_name,
                                "content": content,
                                "create_time": local_time,
                                "user_name": user_name,
                                "thread_title": post_tid.thread.title,
                            })
                break
            except Exception as e:
                print(f"请求失败，尝试第 {attempt + 1} 次重试：{e}")
                attempt += 1
                if attempt < retry_count:
                    wait_time = random.uniform(3, 5)
                    print(f"等待 {wait_time:.2f} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    print("重试次数达到上限，跳过该请求")
    return page_posts

# 获取用户发帖信息并保存
async def fetch_user_posts_by_forum(id_, forum_names, total_count=100, page_size=30, output_file="user_posts.json", BDUSS=""):
    async with tb.Client(BDUSS=BDUSS) as client:
        if forum_names:
            forum_ids = [await client.get_fid(fname) for fname in forum_names]
        else:
            forum_ids = []

        id_ = str(id_)
        if id_.isdigit():
            id__ = await client.tieba_uid2user_info(int(id_))
            id_ = str(id__)

        max_pages = (total_count + page_size - 1) // page_size
        tasks = [fetch_page_posts(client, id_, forum_names, forum_ids, page, page_size) for page in range(1, max_pages + 1)]
        all_page_posts = await asyncio.gather(*tasks)
        all_posts = [post for page_posts in all_page_posts for post in page_posts]

        output_file = generate_output_filename(id_, forum_names, output_type="posts")
        print(f"抓取到的帖子数量: {len(all_posts)}")
        if all_posts:
            async with aiofiles.open(output_file, "w", encoding="utf-8") as file:
                await file.write(json.dumps(all_posts, ensure_ascii=False, indent=4))
        else:
            print("没有抓取到帖子")

        print(f"用户 {id_} 在指定贴吧的所有发言已保存到文件 {output_file}")

# 保存关注的吧信息到文件
async def save_followed_forums(id_, BDUSS, output_file="followed_forums.json"):
    async with tb.Client(BDUSS=BDUSS) as client:
        follow_forums = await fetch_followed_forums(client, id_)
        output_file = generate_output_filename(id_, [], output_type="followed_forums")
        if follow_forums:
            async with aiofiles.open(output_file, "w", encoding="utf-8") as file:
                await file.write(json.dumps(follow_forums, ensure_ascii=False, indent=4))
            print(f"用户 {id_} 的关注贴吧信息已保存到文件 {output_file}")
        else:
            print("没有抓取到关注的贴吧")

def load_config(config_file="config.json"):
    with open(config_file, "r") as file:
        return json.load(file)

if __name__ == "__main__":
    start_time = time.time()

    config = load_config()

    user_id = config["user_id"]
    total_count = config["total_count"]
    forum_names = config["forum_names"]
    BDUSS = config["BDUSS"] 

    asyncio.run(fetch_user_posts_by_forum(user_id, forum_names, total_count=total_count))
    # asyncio.run(save_followed_forums(user_id, BDUSS))

    end_time = time.time()
    total_time = end_time - start_time
    print(f"总共花费时间：{total_time:.2f} 秒")
