#!/usr/bin/python
#*- coding: utf-8 -*-
"""
Sublime Kanboard Plugin
-----------------------
Author: Giuliano Nascimento

This project uses some code and ideas from:
- OpenedFiles plugin with MIT license - https://github.com/qiray/SublimeOpenedFiles
- Sublime FileBrowser plugin with MIT license - https://packagecontrol.io/packages/FileBrowser
- Kanboard Python API with MIT license - https://github.com/kanboard/python-api-client
"""

import sublime
import sublime_plugin

import json
import base64
import functools
from urllib import request as http


DEFAULT_AUTH_HEADER = 'Authorization'

VERSION_MAJOR = 0
VERSION_MINOR = 0
VERSION_PATCH = 1

ST3 = int(sublime.version()) >= 3000

#TODO: add comments

if ST3:
    from .common import UNTITLED_NAME, debug, SYNTAX_EXTENSION
    from .show import show, first
    from .treeview import Tree
    from .GotoWindow import focus_window
else:  # ST2 imports
    from common import UNTITLED_NAME, debug, SYNTAX_EXTENSION
    from show import show, first
    from treeview import Tree
    from GotoWindow import focus_window


swims = []
tasks = []



class ClientError(Exception):
    pass


class Client:
    """
    Kanboard API client

    Example:

    from kanboard import Client

    kb = Client(url="http://localhost/jsonrpc.php",
    username="jsonrpc",
    password="your_api_token")

    project_id = kb.create_project(name="My project")

    """

    def __init__(self,
        url,
        username,
        password,
        auth_header=DEFAULT_AUTH_HEADER,
        cafile=None):
        """
        Constructor

        Args:
        url: API url endpoint
        username: API username or real username
        password: API token or user password
        auth_header: API HTTP header
        cafile: path to a custom CA certificate
        loop: an asyncio event loop. Default: asyncio.get_event_loop()
        """
        self._url = url
        self._username = username
        self._password = password
        self._auth_header = auth_header
        self._cafile = cafile

    def __getattr__(self, name):
        def function(*args, **kwargs):
            return self.execute(method=self._to_camel_case(name), **kwargs)
        return function

    @staticmethod
    def _to_camel_case(snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    @staticmethod
    def _parse_response(response):
        try:
            #body = json.loads(response.decode(errors='ignore'))
            body = json.loads(response.decode(errors='ignore'))

            if 'error' in body:
                message = body.get('error').get('message')
                raise ClientError(message)

            return body.get('result')
        except ValueError:
            return None

    def _do_request(self, headers, body):
        try:
            request = http.Request(self._url,
                headers=headers,
                data=json.dumps(body).encode())
            if self._cafile:
                response = http.urlopen(request, cafile=self._cafile).read()
            else:
                response = http.urlopen(request).read()
        except Exception as e:
            raise ClientError(str(e))
        return self._parse_response(response)

    def execute(self, method, **kwargs):
        """
        Call remote API procedure

        Args:
        method: Procedure name
        kwargs: Procedure named arguments

        Returns:
        Procedure result

        Raises:
        urllib.error.HTTPError: Any HTTP error (Python 3)
        """
        payload = {
            'id': 1,
            'jsonrpc': '2.0',
            'method': method,
            'params': kwargs
        }

        credentials = base64.b64encode('{}:{}'.format(self._username, self._password).encode())
        auth_header_prefix = 'Basic ' if self._auth_header == DEFAULT_AUTH_HEADER else ''
        headers = {
            self._auth_header: auth_header_prefix + credentials.decode(),
            'Content-Type': 'application/json',
        }
        return self._do_request(headers, payload)



class TaskView:

    id = 0
    task = []
    project_id = 0
    swimlane_id = 0
    column_id = 0
    title = ""
    project_title = ""
    swimlane_title = ""
    column_title = ""
    viewType = ""

    def __init__(self, task, viewType):
        self.task = task;
        self.viewType = viewType

    def id(self):
        return self.task['id']
    def file_name(self):
        if 'title' in self.task:
            if 'column' in self.task:
                return self.task['column']+'/'+self.task['title']
            else:
                return self.task['title']
        else:
            return ""
    def name(self):
        if 'name' in self.task:
            return self.task['name']
        else:
            return ""
    def title(self):
        if 'title' in self.task:
            return self.task['title']
        else:
            return ""
    def project_id(self):
        if 'project_id' in self.task:
            return self.task['project_id']
        else:
            return "0"
        return self.task['project_id']
    def column_id(self):
        if 'column_id' in self.task:
            return self.task['column_id']
        else:
            return "0"
    def swimlane_id(self):
        if 'swimlane_id' in self.task:
            return self.task['swimlane_id']
        else:
            return "0"
    def viewType(self):
        return self.viewType












def view_name(view):
    """Function to get view name"""
    result = UNTITLED_NAME
    filename = view.file_name()
    name = view.name()
    if filename is not None and filename != '':
        result = filename
    elif name is not None and name != '':
        result = name
    return result

def generate_trees(view_list, localtrees):
    result = []
    count = 1
    for l in view_list:
        if (len(l) == 0):
            continue
        
        first = True
        for view in l:
            if first:
                temp_tree = Tree(view.name()+"\n")
            else:
                name = view_name(view)
                if view.viewType == "task":
                    temp_tree.add_filename(name, view.id(), is_file=True)
            first = False
        nodes = temp_tree.get_nodes()
        for n in nodes:
            old_node = None
            for tree in localtrees:
                old_node = tree.get_node(n)
                if old_node:
                    break
            new_node = temp_tree.get_node(n)
            if old_node:
                new_node.status = old_node.status
                temp_tree.set_node(n, new_node)
        result.append(temp_tree)
        count += 1
    return result

def draw_view(window, edit, view_object, focus=False, other_window=False):
    plugin_settings = sublime.load_settings('kanboard.sublime-settings')
    group_position = plugin_settings.get('group_position')
    if group_position != 'left' and group_position != 'right':
        group_position = 'left'
    view = show(window, 'Kanboard', other_window=other_window, view_id=KanboardCommand.KANBOARD_VIEW, other_group=group_position,focus=focus)
    if not view:
        KanboardCommand.KANBOARD_VIEW = None
        return
    KanboardCommand.KANBOARD_VIEW = view.id()
    view.set_read_only(False) #Enable edit for pasting result
    view.erase(edit, sublime.Region(0, view.size())) #clear view content
    if isinstance(view_object, list):
        result = ''
        for elm in view_object:
            result += str(elm)
        view.insert(edit, 0, result)
    else:
        view.insert(edit, 0, str(view_object)) #paste result
    view.set_read_only(True) #Disable edit

class KanboardCommand(sublime_plugin.TextCommand): #view.run_command('kanboard')

    KANBOARD_VIEW = None
    trees = []

    def run(self, edit, focus=False, other_window=False):


        s = sublime.load_settings("kanboard.sublime-settings")
        url = s.get("url", "https://localhost/kanboard/jsonrpc.php")
        username = s.get("username", "username")
        password = s.get("password", "password")
        project_id = s.get("project_id", 0)

        kb = Client(url, username, password)
        swims = kb.get_all_swim_lanes(project_id=project_id)
        tasks = kb.get_all_tasks(project_id=project_id, status_id=1)
        colms = kb.get_columns(project_id=project_id)

        window = self.view.window()

        if KanboardListener.current_window is not None and \
            KanboardListener.current_window != window:
            return

        view_list = []
        count = 0
        for swim in swims:
            if swim['is_active'] == '1':
                view_list.append([])
                view_list[count].append(TaskView(swim, 'swimlane'))
                print("swim: "+swim['name'])
                for colm in colms:
                    #print(" colm: "+colm['title'])
                    view_list[count].append(TaskView(colm, 'column'))
                    for task in tasks:
                        #print("Task: "+task['title']+" swim_id:"+task['swimlane_id']+" is_active: "+task['is_active'])
                        if task['swimlane_id'] == swim['id'] and task['column_id'] == colm['id']:
                            task['column'] = colm['title'];
                            print("     task: "+task['column']+'/'+task['title'])
                            view_list[count].append(TaskView(task, 'task'))
                count += 1
        KanboardCommand.trees = generate_trees(view_list, KanboardCommand.trees)
        draw_view(window, edit, KanboardCommand.trees, focus, other_window)





        # window = self.view.window()
        # #if we already have Kanboard window we shouldn't create anymore
        # if KanboardListener.current_window is not None and \
        #     KanboardListener.current_window != window:
        #     return
        # windows = sublime.windows()
        # view_list = []
        # count = 0
        # for win in windows:
        #     view_list.append([])
        #     for view in win.views():
        #         settings = view.settings()
        #         if settings.get("kanboard_type"):
        #             KanboardCommand.KANBOARD_VIEW = view.id()
        #         elif settings.get('dired_path'):
        #             pass
        #         else:
        #             view_list[count].append(view)
        #     count += 1
        # KanboardCommand.trees = generate_trees(view_list, KanboardCommand.trees)
        # draw_view(window, edit, KanboardCommand.trees, focus, other_window)

class KanboardActCommand(sublime_plugin.TextCommand):
    def run(self, edit, act='default'):
        selection = self.view.sel()[0]
        self.open_file(edit, selection, act)

    def open_file(self, edit, selection, act):
        window = self.view.window()
        (row, _) = self.view.rowcol(selection.begin())
        curtree = 0
        length, prevlength = 0, 0
        for tree in KanboardCommand.trees: #calc used tree
            if length > row:
                break
            prevlength = length
            length += tree.size
            curtree += 1
        curtree -= 1
        action = KanboardCommand.trees[curtree].get_action(row - prevlength)
        if action is None:
            return
        if 'id' in action:
            node = KanboardCommand.trees[curtree].nodes[action['id']]
        goto_linenumber = row + 1
        # if action['action'] == 'file' and act == 'default':
        #     for win in sublime.windows():
        #         view = first(win.views(), lambda v: v.id() == action['view_id'])
        #         if view:
        #             focus_window(win, view)
        #             break
        if action['action'] == 'window':
            KanboardCommand.trees[curtree].hidden = not KanboardCommand.trees[curtree].hidden
            draw_view(window, edit, KanboardCommand.trees)
        elif action['action'] == 'fold' and act != 'unfold':
            KanboardCommand.trees[curtree].nodes[action['id']].status = 'unfold'
            draw_view(window, edit, KanboardCommand.trees)
        elif action['action'] == 'unfold' and act != 'fold':
            KanboardCommand.trees[curtree].nodes[action['id']].status = 'fold'
            draw_view(window, edit, KanboardCommand.trees)
        elif act == 'fold' and node.parent is not None and node.parent != '':
            goto_linenumber = KanboardCommand.trees[curtree].nodes[node.parent].stringnum
            KanboardCommand.trees[curtree].nodes[node.parent].status = 'unfold'
            draw_view(window, edit, KanboardCommand.trees)
        elif act == 'unfold' and node.children:
            goto_linenumber = KanboardCommand.trees[curtree].nodes[sorted(node.children)[0]].stringnum
        if goto_linenumber == '':
            goto_linenumber = row + 1
        self.view.run_command("goto_line", {"line": goto_linenumber})

class KanboardOpenExternalCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        selection = self.view.sel()[0]
        (row, col) = self.view.rowcol(selection.begin())
        action = KanboardCommand.tree.get_action(row)
        if action is None:
            return
        node = KanboardCommand.tree.nodes[action['id']]
        self.view.window().run_command("open_dir", {"dir": node.node_id})

# MOUSE ACTIONS:

def mouse_click_actions(view, args):
    s = view.settings()
    if s.get("kanboard_type"):
        view.run_command('kanboard_act') #call user defined command
    elif s.get("dired_path") and not s.get("dired_rename_mode"): #for FileBrowser plugin
        if 'directory' in view.scope_name(view.sel()[0].a):
            command = ("dired_expand", {"toggle": True})
        else:
            command = ("dired_select", {"other_group": True})
        view.run_command(*command)
    else:
        system_command = args["command"] if "command" in args else None
        if system_command:
            system_args = dict({"event": args["event"]}.items())
            system_args.update(dict(args["args"].items()))
            view.run_command(system_command, system_args)

if ST3:
    class MouseDoubleclickCommand(sublime_plugin.TextCommand):
        def run_(self, view, args):
            mouse_click_actions(self.view, args)
else:
    class MouseDoubleclickCommand(sublime_plugin.TextCommand):
        def run_(self, args):
            mouse_click_actions(self.view, args)

# Event listners

def get_kanboard_view():
    windows = sublime.windows()
    for win in windows:
        views = win.views()
        if KanboardCommand.KANBOARD_VIEW is not None:
            view = first(views, lambda v: v.id() == KanboardCommand.KANBOARD_VIEW)
        else:
            view = first(views, lambda v: v.settings().get("kanboard_type"))
        if view:
            return view
    return None

def update_kanboard_view(other_window=False):
    view = get_kanboard_view()
    if view:
        view.run_command('kanboard', {"other_window": other_window})

def is_transient_view(window, view): # from https://github.com/FichteFoll/FileHistory (MIT license)
    if not ST3:
        return False

    if window.get_view_index(view)[1] == -1:
        # If the view index is -1, then this can't be a real view.
        # window.transient_view_in_group is not returning the correct
        # value when we quickly cycle through the quick panel previews.
        return True
    return view == window.transient_view_in_group(window.active_group())

class KanboardListener(sublime_plugin.EventListener):
    current_view = None
    current_window = None
    active_list = {}

    # def on_activated(self, view): #save last opened documents or dired view
    #     settings = view.settings()
    #     if settings.get("kanboard_type"):
    #         KanboardListener.current_window = view.window()
    #     if settings.get("kanboard_type") or settings.get('dired_path'):
    #         self.current_view = view
    #         return
    #     if KanboardListener.current_window == view.window() and not view.id() in KanboardListener.active_list:
    #         KanboardListener.active_list[view.id()] = True
    #         self.on_new(view)

    # def on_close(self, view):
    #     w = sublime.active_window()
    #     if w != KanboardListener.current_window or is_transient_view(w, view) and not view.id() in KanboardListener.active_list:
    #         update_kanboard_view(True)
    #         return
    #     if view.id() in KanboardListener.active_list:
    #         KanboardListener.active_list[view.id()] = False
    #     if not 'kanboard' in view.scope_name(0):
    #         update_kanboard_view()
    #         return
    #     KanboardListener.current_window = None #reset current window
    #     # check if closed view was a single one in group
    #     if ST3:
    #         single = not w.views_in_group(0) or not w.views_in_group(1)
    #     else:
    #         single = ([view.id()] == [v.id() for v in w.views_in_group(0)] or
    #                   [view.id()] == [v.id() for v in w.views_in_group(1)])
    #     if w.num_groups() == 2 and single:
    #         # without timeout ST may crash
    #         sublime.set_timeout(lambda: w.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]}), 300)

    # def on_new(self, view):
    #     kanboard_view = get_kanboard_view()
    #     w = sublime.active_window()
    #     if w != KanboardListener.current_window or not kanboard_view or is_transient_view(w, view):
    #         update_kanboard_view(True)
    #         return
    #     active_view = w.active_view()
    #     num_groups = w.num_groups()
    #     if num_groups >= 2:
    #         for i in range(0, num_groups):
    #             if not is_any_kanboard_in_group(w, i):
    #                 w.focus_view(self.current_view) #focus on dired/opened documents view to prevent from strange views' switching
    #                 w.set_view_index(view, i, len(w.views_in_group(i)))
    #                 w.focus_view(view)
    #                 break
    #     update_kanboard_view()

    # def on_load(self, view):
    #     w = sublime.active_window()
    #     if w != KanboardListener.current_window:
    #         update_kanboard_view(True)
    #         return
    #     self.on_new(view)

    # def on_clone(self, view):
    #     w = sublime.active_window()
    #     if w != KanboardListener.current_window:
    #         update_kanboard_view(True)
    #         return
    #     self.on_new(view)

    # def on_post_save_async(self, view):
    #     w = sublime.active_window()
    #     if w != KanboardListener.current_window:
    #         update_kanboard_view(True)
    #         return
    #     self.on_new(view)

def plugin_loaded(): #this function autoruns on plugin loaded
    view = get_kanboard_view()
    if view is not None:
        view.run_command('kanboard')
        window = view.window()
        KanboardListener.current_window = window
        for v in window.views():
            settings = v.settings()
            if settings.get("kanboard_type") or settings.get('dired_path'):
                continue
            if not v.id() in KanboardListener.active_list:
                KanboardListener.active_list[v.id()] = True

def is_any_kanboard_in_group(window, group):
    syntax = 'Packages/Kanboard/kanboard%s' % SYNTAX_EXTENSION
    return any(v.settings().get('syntax') == syntax for v in window.views_in_group(group))
