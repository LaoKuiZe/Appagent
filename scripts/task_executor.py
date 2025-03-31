import argparse
import ast
import datetime
import json
import os
import re
import sys
import time

import prompts
from config import load_config
from and_controller import list_all_devices, AndroidController, traverse_tree
from model import parse_explore_rsp, parse_grid_rsp, OpenAIModel, QwenModel, parse_main_rsp
from utils import print_with_color, draw_bbox_multi, draw_grid
from sub_task import subtask

arg_desc = "AppAgent Executor"
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=arg_desc)
parser.add_argument("--app")
parser.add_argument("--root_dir", default="./")
args = vars(parser.parse_args())

configs = load_config()

if configs["MODEL"] == "OpenAI":
    mllm = OpenAIModel(base_url=configs["OPENAI_API_BASE"],
                       api_key=configs["OPENAI_API_KEY"],
                       model=configs["OPENAI_API_MODEL"],
                       temperature=configs["TEMPERATURE"],
                       max_tokens=configs["MAX_TOKENS"])
elif configs["MODEL"] == "Qwen":
    mllm = QwenModel(api_key=configs["DASHSCOPE_API_KEY"],
                     model=configs["QWEN_MODEL"])
else:
    print_with_color(f"ERROR: Unsupported model type {configs['MODEL']}!", "red")
    sys.exit()

# 开始进行任务交互
print_with_color("Please enter the description of the task you want me to complete in a few sentences:", "blue")
main_desc = input()
main_prompt = re.sub(r"<task_description>", main_desc, prompts.main_task_template)

# task_desc = input()

# 先获取主任务的文本回答(目前可以按照prompt要求生成回答)
main_status, main_task_response = mllm.get_main_response(main_prompt)
main_task_response = main_task_response.replace("**","")
if not main_status:
    print_with_color(f"ERROR: Main task response failed: {main_task_response}", "red")
    sys.exit()
else:
    try:
        # 使用正则表达式提取三个部分
        answer = re.search(r'Answer:(.*?)(?=App:|$)', main_task_response, re.DOTALL).group(1).strip()
        app_match = re.search(r'App:(.*?)(?=Sub-tasks:|$)', main_task_response, re.DOTALL)
        app = app_match.group(1).strip() if app_match else "None"
        
        subtasks_match = re.search(r'Sub-tasks:(.*?)$', main_task_response, re.DOTALL)
        subtasks = subtasks_match.group(1).strip() if subtasks_match else ""
        
        print_with_color(f"Answer: {answer}", "green")
        print_with_color(f"Selected app(s): {app}", "green")
        if subtasks:
            print_with_color(f"Sub-tasks: {subtasks}", "green")

        # 分别提取每个应用的子任务
        app_tasks = {}
        if subtasks:
            # 先检查是否是只有一个应用的情况
            if app.lower() != "both" and app.lower() != "none" and ":" not in subtasks:
                # 这是只有一个应用的情况，整个subtasks都是给这个应用的
                app_tasks[app] = subtasks
            else:
                # 使用更鲁棒的正则表达式匹配应用名称和对应的任务
                app_task_matches = re.findall(r'[-\s]*([^:]+):\s*(.*?)(?=\n\s*[-]*\s*[^:]+:|$)', subtasks, re.DOTALL)
                for app_name, task in app_task_matches:
                    app_tasks[app_name.strip()] = task.strip()
        
        print_with_color(f"Answer: {answer}", "green")
        print_with_color(f"Selected app(s): {app}", "blue")
            
        # 打印每个应用的子任务
        for app_name, task in app_tasks.items():
            print_with_color(f"{app_name} task: {task}", "cyan")

        # 根据选择的应用继续执行，而不是退出
        task_desc = main_desc  # 使用原始任务描述
    except Exception as e:
        print_with_color(f"ERROR: Failed to parse main task response: {str(e)}", "red")
        sys.exit()

#sys.exit()

# 完成后，获取子任务的文本回答，配置相关的参数
while(True):
    if len(app_tasks) == 0:
        sys.exit()
    elif len(app_tasks) == 1:  # 使用app_tasks而不是subtasks检查数量
        app = list(app_tasks.keys())[0]  # 将keys()转换为列表
        task_desc = f"First, tap the icon of {app}." + app_tasks[app]
        print_with_color(f"The app is {app}", "yellow")
        print_with_color(f"Task description: {task_desc}", "yellow")
        app = app.lower()
        result_path = subtask(app, task_desc)
        print_with_color(f"\n\nAll task completed successfully!", "blue")
        print_with_color(f"{main_task_response}", "blue")
        print_with_color(f"The {app} screenshot path is {result_path}", "yellow")
        sys.exit()
    elif len(app_tasks) == 2:
        app_names = list(app_tasks.keys())
        app1 = app_names[0]
        app2 = app_names[1]
        task_desc1 = f"First, tap the icon of {app1}." +app_tasks[app1]
        task_desc2 = f"First, tap the icon of {app2}." +app_tasks[app2]
        print(f"Task description for {app1}: {task_desc1}")
        print(f"Task description for {app2}: {task_desc2}")
        # 这里要修改为返回截图路径
        app1 = app1.lower()
        app2 = app2.lower()
        result_path1 = subtask(app1, task_desc)

        # 创建一个新的控制器实例
        device_list = list_all_devices()
        if device_list:
            device = device_list[0]
            controller = AndroidController(device)
            # 返回主屏幕准备执行下一个任务
            print_with_color(f"返回主屏幕并准备执行下一个任务...", "yellow")
            controller.home()
            time.sleep(2)  # 给系统一些时间完全回到主页

        result_path2 = subtask(app2, task_desc)

        print_with_color(f"\n\nAll task completed successfully!", "blue")
        print_with_color(f"{main_task_response}", "blue")
        print_with_color(f"The {app1} screenshot path is {result_path1}", "blue")
        print_with_color(f"The {app2} screenshot path is {result_path2}", "blue")
        sys.exit()


        

# 下面的代码作为子任务单独放在suntask函数中
# app = args["app"]
# root_dir = args["root_dir"]

# # if not app:
# #     print_with_color("What is the name of the app you want me to operate?", "blue")
# #     app = input()
# #     app = app.replace(" ", "")

# app_dir = os.path.join(os.path.join(root_dir, "apps"), app)
# work_dir = os.path.join(root_dir, "tasks")
# if not os.path.exists(work_dir):
#     os.mkdir(work_dir)
# auto_docs_dir = os.path.join(app_dir, "auto_docs")
# demo_docs_dir = os.path.join(app_dir, "demo_docs")
# task_timestamp = int(time.time())
# dir_name = datetime.datetime.fromtimestamp(task_timestamp).strftime(f"task_{app}_%Y-%m-%d_%H-%M-%S")
# task_dir = os.path.join(work_dir, dir_name)
# os.mkdir(task_dir)
# log_path = os.path.join(task_dir, f"log_{app}_{dir_name}.txt")

# no_doc = False
# if not os.path.exists(auto_docs_dir) and not os.path.exists(demo_docs_dir):
#     print_with_color(f"No documentations found for the app {app}. Do you want to proceed with no docs? Enter y or n",
#                      "red")
#     user_input = ""
#     while user_input != "y" and user_input != "n":
#         user_input = input().lower()
#     if user_input == "y":
#         no_doc = True
#     else:
#         sys.exit()
# elif os.path.exists(auto_docs_dir) and os.path.exists(demo_docs_dir):
#     print_with_color(f"The app {app} has documentations generated from both autonomous exploration and human "
#                      f"demonstration. Which one do you want to use? Type 1 or 2.\n1. Autonomous exploration\n2. Human "
#                      f"Demonstration",
#                      "blue")
#     user_input = ""
#     while user_input != "1" and user_input != "2":
#         user_input = input()
#     if user_input == "1":
#         docs_dir = auto_docs_dir
#     else:
#         docs_dir = demo_docs_dir
# elif os.path.exists(auto_docs_dir):
#     print_with_color(f"Documentations generated from autonomous exploration were found for the app {app}. The doc base "
#                      f"is selected automatically.", "yellow")
#     docs_dir = auto_docs_dir
# else:
#     print_with_color(f"Documentations generated from human demonstration were found for the app {app}. The doc base is "
#                      f"selected automatically.", "yellow")
#     docs_dir = demo_docs_dir

# device_list = list_all_devices()
# if not device_list:
#     print_with_color("ERROR: No device found!", "red")
#     sys.exit()
# print_with_color(f"List of devices attached:\n{str(device_list)}", "yellow")
# if len(device_list) == 1:
#     device = device_list[0]
#     print_with_color(f"Device selected: {device}", "yellow")
# else:
#     print_with_color("Please choose the Android device to start demo by entering its ID:", "blue")
#     device = input()
# controller = AndroidController(device)
# width, height = controller.get_device_size()
# if not width and not height:
#     print_with_color("ERROR: Invalid device size!", "red")
#     sys.exit()
# print_with_color(f"Screen resolution of {device}: {width}x{height}", "yellow")

# # 初始化记录参数
# round_count = 0
# last_act = "None"
# task_complete = False
# grid_on = False
# rows, cols = 0, 0


# def area_to_xy(area, subarea):
#     area -= 1
#     row, col = area // cols, area % cols
#     x_0, y_0 = col * (width // cols), row * (height // rows)
#     if subarea == "top-left":
#         x, y = x_0 + (width // cols) // 4, y_0 + (height // rows) // 4
#     elif subarea == "top":
#         x, y = x_0 + (width // cols) // 2, y_0 + (height // rows) // 4
#     elif subarea == "top-right":
#         x, y = x_0 + (width // cols) * 3 // 4, y_0 + (height // rows) // 4
#     elif subarea == "left":
#         x, y = x_0 + (width // cols) // 4, y_0 + (height // rows) // 2
#     elif subarea == "right":
#         x, y = x_0 + (width // cols) * 3 // 4, y_0 + (height // rows) // 2
#     elif subarea == "bottom-left":
#         x, y = x_0 + (width // cols) // 4, y_0 + (height // rows) * 3 // 4
#     elif subarea == "bottom":
#         x, y = x_0 + (width // cols) // 2, y_0 + (height // rows) * 3 // 4
#     elif subarea == "bottom-right":
#         x, y = x_0 + (width // cols) * 3 // 4, y_0 + (height // rows) * 3 // 4
#     else:
#         x, y = x_0 + (width // cols) // 2, y_0 + (height // rows) // 2
#     return x, y

# # 开始运行agent
# while round_count < configs["MAX_ROUNDS"]:
#     round_count += 1
#     print_with_color(f"Round {round_count}", "yellow")
#     screenshot_path = controller.get_screenshot(f"{dir_name}_{round_count}", task_dir)
#     xml_path = controller.get_xml(f"{dir_name}_{round_count}", task_dir)
#     if screenshot_path == "ERROR" or xml_path == "ERROR":
#         break
#     if grid_on:
#         rows, cols = draw_grid(screenshot_path, os.path.join(task_dir, f"{dir_name}_{round_count}_grid.png"))
#         image = os.path.join(task_dir, f"{dir_name}_{round_count}_grid.png")
#         prompt = prompts.task_template_grid
#     else:
#         clickable_list = []
#         focusable_list = []
#         traverse_tree(xml_path, clickable_list, "clickable", True)
#         traverse_tree(xml_path, focusable_list, "focusable", True)
#         elem_list = clickable_list.copy()
#         for elem in focusable_list:
#             bbox = elem.bbox
#             center = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
#             close = False
#             for e in clickable_list:
#                 bbox = e.bbox
#                 center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
#                 dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
#                 if dist <= configs["MIN_DIST"]:
#                     close = True
#                     break
#             if not close:
#                 elem_list.append(elem)
#         draw_bbox_multi(screenshot_path, os.path.join(task_dir, f"{dir_name}_{round_count}_labeled.png"), elem_list,
#                         dark_mode=configs["DARK_MODE"])
#         image = os.path.join(task_dir, f"{dir_name}_{round_count}_labeled.png")

#         # 构造任务prompt
#         if no_doc:
#             prompt = re.sub(r"<ui_document>", "", prompts.task_template)
#         else:
#             ui_doc = ""
#             for i, elem in enumerate(elem_list):
#                 doc_path = os.path.join(docs_dir, f"{elem.uid}.txt")
#                 if not os.path.exists(doc_path):
#                     continue
#                 ui_doc += f"Documentation of UI element labeled with the numeric tag '{i + 1}':\n"
#                 doc_content = ast.literal_eval(open(doc_path, "r").read())
#                 if doc_content["tap"]:
#                     ui_doc += f"This UI element is clickable. {doc_content['tap']}\n\n"
#                 if doc_content["text"]:
#                     ui_doc += f"This UI element can receive text input. The text input is used for the following " \
#                               f"purposes: {doc_content['text']}\n\n"
#                 if doc_content["long_press"]:
#                     ui_doc += f"This UI element is long clickable. {doc_content['long_press']}\n\n"
#                 if doc_content["v_swipe"]:
#                     ui_doc += f"This element can be swiped directly without tapping. You can swipe vertically on " \
#                               f"this UI element. {doc_content['v_swipe']}\n\n"
#                 if doc_content["h_swipe"]:
#                     ui_doc += f"This element can be swiped directly without tapping. You can swipe horizontally on " \
#                               f"this UI element. {doc_content['h_swipe']}\n\n"
#             print_with_color(f"Documentations retrieved for the current interface:\n{ui_doc}", "magenta")
#             ui_doc = """
#             You also have access to the following documentations that describes the functionalities of UI 
#             elements you can interact on the screen. These docs are crucial for you to determine the target of your 
#             next action. You should always prioritize these documented elements for interaction:""" + ui_doc
#             prompt = re.sub(r"<ui_document>", ui_doc, prompts.task_template)
#     prompt = re.sub(r"<task_description>", task_desc, prompt)
#     prompt = re.sub(r"<last_act>", last_act, prompt)
#     print_with_color("Thinking about what to do in the next step...", "yellow")
#     status, rsp = mllm.get_model_response(prompt, [image])

#     if status:
#         with open(log_path, "a") as logfile:
#             log_item = {"step": round_count, "prompt": prompt, "image": f"{dir_name}_{round_count}_labeled.png",
#                         "response": rsp}
#             logfile.write(json.dumps(log_item) + "\n")
#         if grid_on:
#             res = parse_grid_rsp(rsp)
#         else:
#             res = parse_explore_rsp(rsp)
#         act_name = res[0]
#         if act_name == "FINISH":
#             task_complete = True
#             break
#         if act_name == "ERROR":
#             break
#         last_act = res[-1]
#         res = res[:-1]
#         if act_name == "tap":
#             _, area = res
#             tl, br = elem_list[area - 1].bbox
#             x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
#             ret = controller.tap(x, y)
#             if ret == "ERROR":
#                 print_with_color("ERROR: tap execution failed", "red")
#                 break
#         elif act_name == "text":
#             _, input_str = res
#             ret = controller.text(input_str)
#             if ret == "ERROR":
#                 print_with_color("ERROR: text execution failed", "red")
#                 break
#         elif act_name == "long_press":
#             _, area = res
#             tl, br = elem_list[area - 1].bbox
#             x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
#             ret = controller.long_press(x, y)
#             if ret == "ERROR":
#                 print_with_color("ERROR: long press execution failed", "red")
#                 break
#         elif act_name == "swipe":
#             _, area, swipe_dir, dist = res
#             tl, br = elem_list[area - 1].bbox
#             x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
#             ret = controller.swipe(x, y, swipe_dir, dist)
#             if ret == "ERROR":
#                 print_with_color("ERROR: swipe execution failed", "red")
#                 break
#         elif act_name == "grid":
#             grid_on = True
#         elif act_name == "tap_grid" or act_name == "long_press_grid":
#             _, area, subarea = res
#             x, y = area_to_xy(area, subarea)
#             if act_name == "tap_grid":
#                 ret = controller.tap(x, y)
#                 if ret == "ERROR":
#                     print_with_color("ERROR: tap execution failed", "red")
#                     break
#             else:
#                 ret = controller.long_press(x, y)
#                 if ret == "ERROR":
#                     print_with_color("ERROR: tap execution failed", "red")
#                     break
#         elif act_name == "swipe_grid":
#             _, start_area, start_subarea, end_area, end_subarea = res
#             start_x, start_y = area_to_xy(start_area, start_subarea)
#             end_x, end_y = area_to_xy(end_area, end_subarea)
#             ret = controller.swipe_precise((start_x, start_y), (end_x, end_y))
#             if ret == "ERROR":
#                 print_with_color("ERROR: tap execution failed", "red")
#                 break
#         if act_name != "grid":
#             grid_on = False
#         time.sleep(configs["REQUEST_INTERVAL"])
#     else:
#         print_with_color(rsp, "red")
#         break

# if task_complete:
#     print_with_color("Task completed successfully", "yellow")
# elif round_count == configs["MAX_ROUNDS"]:
#     print_with_color("Task finished due to reaching max rounds", "yellow")
# else:
#     print_with_color("Task finished unexpectedly", "red")
