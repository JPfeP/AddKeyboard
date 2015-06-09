#    This Addon for Blender allows the use of a second keybord as a
#    dedicated controler.
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#    Copyright (C) 2014  JPfeP <http://www.jpfep.net/>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ***** END GPL LICENCE BLOCK ***** 
 
#faire en sorte que lorsqu'on ouvre la liste elle refresh les devices USB
#utiliser grab() et ungrab()
#le fait d'avoir une prop de scene ne va t il pas foutre la merde quand on changera de scene ?
#100ms trop peu ?
#attention au niveau du panel il faut que l'état des boutons on/off soit cohérent avec si le process tourne, quand on change de scene/blend
#pbm de circularité au debut : quand on read le fichier de conf ca actualise la propenum, ca declenche upd() qui dump le fichier de conf
#attention quand on débranche la clavier et rebranche, pas retrouvé apres , changement d'ID sournois ?
#Gerer le fait que les fichiers de conf soient manquants = plein d'erreur a cause de REFRESH
#la sauvegarde automatique fait encore chier à fair des fichiers de 22megas

#bpy.context.area.type = 'INFO' 

#bpy.ops.info.select_all_toggle()
#bpy.ops.info.report_delete()
#bpy.ops.info.report_copy()
#a=bpy.context.window_manager.clipboard
#bpy.ops.info.select_pick(report_index=0,3)
#bpy.ops.info.reports_display_update()
#print (len(a.split("\n")))


bl_info = {
    "name": "AddKeyboard",
    "author": "J.P.P",
    "version": (0, 3),
    "blender": (2, 6, 4),
    "location": "",
    "description": "Associate the keys of a dedicated keyboard to the blender functions of your choice",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "System"}


import bpy
from sys import exit
from select import select
from evdev import ecodes, InputDevice, list_devices
from bpy.utils import register_module, unregister_module
from bpy.app.handlers import persistent
import threading
import time

dedikb_list= []
dedikb_prefs=[] 
device=''
last_event=0

#bpy.context.area.type = 'TEXT_EDITOR'
#bpy.ops.text.run_script()

from asyncore import file_dispatcher, loop
from evdev import InputDevice, categorize, ecodes
 

class InputDeviceDispatcher(file_dispatcher):
     def __init__(self, device):
         self.device = device
         file_dispatcher.__init__(self, device)

     def recv(self, ign=None):
         return self.device.read()

     def handle_read(self):
         for event in self.recv():
             print(repr(event))
  

class KB_UIPanel(bpy.types.Panel):
    bl_label = "AddKeyboard"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "AddKeyboard"
     
    bpy.types.Scene.on_off = bpy.props.BoolProperty()
 
    def draw(self, context):                         
        self.layout.operator("addkeyboard.modal_timer_operator", text='Start')
        self.layout.prop(bpy.context.scene, 'on_off', text='Auto run')
        self.layout.prop(bpy.context.scene , 'input_dev')
        self.layout.operator("addkeyboard.keypopup" , text='Key editor')
            
def refresh_list(description="-1"):
        b=[]
        b.append(("REFRESH","----------REFRESH LIST----------",""))
        devices = map(InputDevice, list_devices())
        for i in devices:
            a = (i.fn,i.name,i.phys)
            if description == i.phys:
                return i.fn
            b.append(a)
        return b
    
def readlists():
    print("AddKeyboard: Reading config files")
    path = bpy.utils.resource_path('USER')+"/config/"
    
    global dedikb_list, dedikb_prefs
    
    #for the list of keys
    try:
        file = open(path+'addkeyboard_list.cfg','r')
        for line in file.readlines():
            dedikb_list.append(line[:-1]) #to remove the RETURN caracter
        file.close()
    except:
        print ("AddKeyboard: no list file found")
        dedikb_list= [""] * 150
    
    #for the addon prefs
    try: 
        file = open(path+'addkeyboard_prefs.cfg','r')
        for line in file.readlines():
            dedikb_prefs.append(line[:-1]) #to remove the RETURN caracter
        file.close()
        #restoring the users prefs
        bpy.context.scene.input_dev = refresh_list(dedikb_prefs[0])
    except:
        print ("AddKeyboard: no config file found")
        dedikb_prefs=[""] * 5
   
    
def writelists():
    print("AddKeyboard: Saving")
    path = bpy.utils.resource_path('USER')+"/config/"
        
    #for the list of keys
    file = open(path+'addkeyboard_list.cfg','w')                       
    for eachitem in dedikb_list:
        file.write(eachitem+"\n")        
    file.close()
    
    #for the addon prefs
    file = open(path+'addkeyboard_prefs.cfg','w')                       
    for eachitem in dedikb_prefs:
        file.write(eachitem+"\n")        
    file.close()
                   
class SelectDevice(bpy.types.Operator):  
    bl_label = "Find the devices"
    bl_idname = "addkeyboard.devices"
    
    dev_list_enum = []
    dev_list_enum.extend(refresh_list())
     
    global device      
            
    def upd(self, context): 
        if bpy.context.scene.input_dev == "REFRESH":
            dev_list_enum = refresh_list()
        else:
            device = bpy.types.Scene.input_dev
            dedikb_prefs[0] = bpy.types.Scene.bl_rna.properties['input_dev'].enum_items[bpy.context.scene.input_dev].description
            writelists()
            #device.grab()    

    bpy.types.Scene.input_dev = bpy.props.EnumProperty(name = "input devices", items = dev_list_enum, update=upd) 
    


class DedicatedKB(bpy.types.Operator):
    '''Command Blender with a dedicated keyboard'''
    bl_idname = "addkeyboard.modal_timer_operator"
    bl_label = "DedicatedKB"    
   
    _timer = None
          
    def modal(self, context, event):
        global last_event 
        if event.type == 'ESC':
            return self.cancel(context)        
        if event.type == 'TIMER':    
            r, w, e = select([self.device], [], [], 0)   # the last 0 arg is for non-blocking
            for i in range (0,3):                   #each keystroke produces 3 lines
                ev = self.device.read_one()
                if str(ev) == "None" : break
                elif ev.type == 1 and ev.value == 1:
                    print(ev.code)
                     
                    exec(dedikb_list[ev.code])
                    last_event=ev.code                  
        return {'PASS_THROUGH'}            
          
    def execute(self, context):
        self.device = InputDevice(bpy.context.scene.input_dev)
        try:
            self.device.grab()
        except:
            pass
        InputDeviceDispatcher(self.device)
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(.1, context.window)
        print('reading events')
        return {'RUNNING_MODAL'}        

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        print('reading stopped')
        return {'CANCELLED'}


#class MessageKeyOperator(bpy.types.Operator):
class DialogOperator(bpy.types.Operator):
    bl_idname = "addkeyboard.keypopup"
    bl_label = "AddKeyboard Keys Tool"
     
    command = bpy.props.StringProperty()
    value = bpy.props.IntProperty()
      
    def execute(self, context):
       
        dedikb_list[self.value]= self.command
        writelists()
       
        return {'FINISHED'}
 
    def invoke(self, context, event):
        global last_event
                
        self.command = dedikb_list[self.value] 
        self.value = last_event 
         
        return context.window_manager.invoke_props_dialog(self, width=1000, height=200)
 

class HelloWorldPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Hello World Panel"
    bl_idname = "OBJECT_PT_hello"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
 
    def draw(self, context):
        layout = self.layout
 
        # If Scene.my_prop wasn't created in register() or removed, draw a note
        if not hasattr(context.scene, "my_prop"):
            layout.label("Scene does not have a property 'my_prop'")
 
        # If it has no longer the default property value, draw a label with icon
        elif context.scene.my_prop != 'default value':
            layout.label("my_prop = " + context.scene.my_prop, icon="FILE_TICK")
 
        # It has the default property value, draw a label with no icon
        else:
            layout.label("my_propal = " + context.scene.my_prop)
            #bpy.ops.addkeyboard.modal_timer_operator()
 
        layout.operator(InitMyPropOperator.bl_idname, text=InitMyPropOperator.bl_label)

 
class InitMyPropOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "scene.init_my_prop"
    bl_label = "Init my_prop"
 
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
 
    def execute(self, context):
        if context.scene.my_prop != "initialized":
            context.scene.my_prop = "initialized"
            self.__class__.bl_label = "Change my_prop"
        else:
            context.scene.my_prop = "foobar"
            self.__class__.bl_label = self.bl_label
        return {'FINISHED'}


@persistent
def my_handler2(scene):
    readlists()
    bpy.ops.addkeyboard.modal_timer_operator()
    bpy.app.handlers.frame_change_post.remove(my_handler2)
 
@persistent
def my_handler(scene):
    bpy.app.handlers.frame_change_post.append(my_handler2)
    bpy.context.scene.frame_current=bpy.context.scene.frame_current
    bpy.app.handlers.scene_update_post.remove(my_handler)

def register():
    bpy.utils.register_module(__name__)         
    bpy.types.Scene.my_prop = bpy.props.StringProperty(default="default value")
    bpy.app.handlers.scene_update_post.append(my_handler)

def unregister():
    bpy.utils.unregister_module(__name__)
 
if __name__ == "__main__": 
    register()
 
 

