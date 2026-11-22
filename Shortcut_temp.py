import threading
import time

class Shortcut():
    
    global HOTKEYS
    global ACTIONS
    global KEY_STATUS
    global PRESSED_COUNT
    
    HOTKEYS = {}
    ACTIONS = {}
    KEY_STATUS = {}
    PRESSED_COUNT = {}
    
    def __init__(self):
        pass
        
    def add(self, key_group_id , key_group, action):    
        global HOTKEYS
        global ACTIONS
        
        HOTKEYS[key_group_id] = key_group
        ACTIONS[key_group_id] = action
        
    def clear(self):
        HOTKEYS.clear()
        ACTIONS.clear()

    def monitor(self):
        print("快捷键监控功能暂时禁用 - 请使用右键菜单操作")
        # 临时禁用PyHook3相关功能
        pass