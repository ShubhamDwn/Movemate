from ast import Break
import tkinter
import customtkinter
from PIL import ImageTk, Image


customtkinter.set_appearance_mode("DARK")
customtkinter.set_default_color_theme("blue")

root = customtkinter.CTk()
root.geometry("1000x700")
root.title("MOVEMATE")

current_frame = None


def tab1():
    def tab2():
        pass


def start():
    import cv2
    import mediapipe as mp
    import pyautogui
    import math
    from enum import IntEnum
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from google.protobuf.json_format import MessageToDict
    import screen_brightness_control as sbcontrol

    pyautogui.FAILSAFE = False
    mp_drawing = mp.solutions.drawing_utils
    mp_hands = mp.solutions.hands

    # Gesture Encodings 
    class Gest(IntEnum):
        # Binary Encoded
        # Enum for mapping all hand gesture to binary number.
        FIST = 0
        PINKY = 1
        RING = 2
        MID = 4
        LAST3 = 7
        INDEX = 8
        FIRST2 = 12
        LAST4 = 15
        THUMB = 16    
        PALM = 31
        
        # Extra Mappings
        V_GEST = 33
        TWO_FINGER_CLOSED = 34
        PINCH_MAJOR = 35
        PINCH_MINOR = 36

    # Multi-handedness Labels
    class HLabel(IntEnum):
        MINOR = 0
        MAJOR = 1

    # Convert Mediapipe Landmarks to recognizable Gestures
    class HandRecog:
        def __init__(self, hand_label):

            self.finger = 0
            self.ori_gesture = Gest.PALM
            self.prev_gesture = Gest.PALM
            self.frame_count = 0
            self.hand_result = None
            self.hand_label = hand_label
        
        def update_hand_result(self, hand_result):
            self.hand_result = hand_result

        def get_signed_dist(self, point):
            sign = -1
            if self.hand_result.landmark[point[0]].y < self.hand_result.landmark[point[1]].y:
                sign = 1
            dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x)**2
            dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y)**2
            dist = math.sqrt(dist)
            return dist*sign
        
        def get_dist(self, point):
            dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x)**2
            dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y)**2
            dist = math.sqrt(dist)
            return dist
        
        def get_dz(self,point):
            return abs(self.hand_result.landmark[point[0]].z - self.hand_result.landmark[point[1]].z)
        # Function to find Gesture Encoding using current finger_state.
        # Finger_state: 1 if finger is open, else 0
        def set_finger_state(self):
            if self.hand_result == None:
                return
            points = [[8,5,0],[12,9,0],[16,13,0],[20,17,0]]
            self.finger = 0
            self.finger = self.finger | 0 #thumb
            for idx,point in enumerate(points):
                
                dist = self.get_signed_dist(point[:2])
                dist2 = self.get_signed_dist(point[1:])
                
                try:
                    ratio = round(dist/dist2,1)
                except:
                    ratio = round(dist1/0.01,1)

                self.finger = self.finger << 1
                if ratio > 0.5 :
                    self.finger = self.finger | 1
        

        # Handling Fluctations due to noise
        def get_gesture(self):
            if self.hand_result == None:
                return Gest.PALM

            current_gesture = Gest.PALM
            if self.finger in [Gest.LAST3,Gest.LAST4] and self.get_dist([8,4]) < 0.05:
                if self.hand_label == HLabel.MINOR :
                    current_gesture = Gest.PINCH_MINOR
                else:
                    current_gesture = Gest.PINCH_MAJOR

            elif Gest.FIRST2 == self.finger :
                point = [[8,12],[5,9]]
                dist1 = self.get_dist(point[0])
                dist2 = self.get_dist(point[1])
                ratio = dist1/dist2
                if ratio > 1.7:
                    current_gesture = Gest.V_GEST
                else:
                    if self.get_dz([8,12]) < 0.1:
                        current_gesture =  Gest.TWO_FINGER_CLOSED
                    else:
                        current_gesture =  Gest.MID
                
            else:
                current_gesture =  self.finger
            
            if current_gesture == self.prev_gesture:
                self.frame_count += 1
            else:
                self.frame_count = 0

            self.prev_gesture = current_gesture

            if self.frame_count > 4 :
                self.ori_gesture = current_gesture
            return self.ori_gesture

    # Executes commands according to detected gestures
    class Controller:
        tx_old = 0
        ty_old = 0
        trial = True
        flag = False
        grabflag = False
        pinchmajorflag = False
        pinchminorflag = False
        pinchstartxcoord = None
        pinchstartycoord = None
        pinchdirectionflag = None
        prevpinchlv = 0
        pinchlv = 0
        framecount = 0
        prev_hand = None
        pinch_threshold = 0.3
        
        def getpinchylv(hand_result):
            """returns distance beween starting pinch y coord and current hand position y coord."""
            dist = round((Controller.pinchstartycoord - hand_result.landmark[8].y)*10,1)
            return dist

        def getpinchxlv(hand_result):
            """returns distance beween starting pinch x coord and current hand position x coord."""
            dist = round((hand_result.landmark[8].x - Controller.pinchstartxcoord)*10,1)
            return dist
        
        def changesystembrightness():
            """sets system brightness based on 'Controller.pinchlv'."""
            currentBrightnessLv = sbcontrol.get_brightness(display=0)/100.0
            currentBrightnessLv += Controller.pinchlv/50.0
            if currentBrightnessLv > 1.0:
                currentBrightnessLv = 1.0
            elif currentBrightnessLv < 0.0:
                currentBrightnessLv = 0.0       
            sbcontrol.fade_brightness(int(100*currentBrightnessLv) , start = sbcontrol.get_brightness(display=0))
        
        def changesystemvolume():
            """sets system volume based on 'Controller.pinchlv'."""
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            currentVolumeLv = volume.GetMasterVolumeLevelScalar()
            currentVolumeLv += Controller.pinchlv/50.0
            if currentVolumeLv > 1.0:
                currentVolumeLv = 1.0
            elif currentVolumeLv < 0.0:
                currentVolumeLv = 0.0
            volume.SetMasterVolumeLevelScalar(currentVolumeLv, None)
        
        def scrollVertical():
            """scrolls on screen vertically."""
            pyautogui.scroll(120 if Controller.pinchlv>0.0 else -120)
            
        
        def scrollHorizontal():
            """scrolls on screen horizontally."""
            pyautogui.keyDown('shift')
            pyautogui.keyDown('ctrl')
            pyautogui.scroll(-120 if Controller.pinchlv>0.0 else 120)
            pyautogui.keyUp('ctrl')
            pyautogui.keyUp('shift')

        # Locate Hand to get Cursor Position
        # Stabilize cursor by Dampening
        def get_position(hand_result):
            point = 9
            position = [hand_result.landmark[point].x ,hand_result.landmark[point].y]
            sx,sy = pyautogui.size()
            x_old,y_old = pyautogui.position()
            x = int(position[0]*sx)
            y = int(position[1]*sy)
            if Controller.prev_hand is None:
                Controller.prev_hand = x,y
            delta_x = x - Controller.prev_hand[0]
            delta_y = y - Controller.prev_hand[1]

            distsq = delta_x**2 + delta_y**2
            ratio = 1
            Controller.prev_hand = [x,y]

            if distsq <= 25:
                ratio = 0
            elif distsq <= 900:
                ratio = 0.07 * (distsq ** (1/2))
            else:
                ratio = 2.1
            x , y = x_old + delta_x*ratio , y_old + delta_y*ratio
            return (x,y)

        def pinch_control_init(hand_result):
            """Initializes attributes for pinch gesture."""
            Controller.pinchstartxcoord = hand_result.landmark[8].x
            Controller.pinchstartycoord = hand_result.landmark[8].y
            Controller.pinchlv = 0
            Controller.prevpinchlv = 0
            Controller.framecount = 0

        # Hold final position for 5 frames to change status
        def pinch_control(hand_result, controlHorizontal, controlVertical):
            if Controller.framecount == 5:
                Controller.framecount = 0
                Controller.pinchlv = Controller.prevpinchlv

                if Controller.pinchdirectionflag == True:
                    controlHorizontal() #x

                elif Controller.pinchdirectionflag == False:
                    controlVertical() #y

            lvx =  Controller.getpinchxlv(hand_result)
            lvy =  Controller.getpinchylv(hand_result)
                
            if abs(lvy) > abs(lvx) and abs(lvy) > Controller.pinch_threshold:
                Controller.pinchdirectionflag = False
                if abs(Controller.prevpinchlv - lvy) < Controller.pinch_threshold:
                    Controller.framecount += 1
                else:
                    Controller.prevpinchlv = lvy
                    Controller.framecount = 0

            elif abs(lvx) > Controller.pinch_threshold:
                Controller.pinchdirectionflag = True
                if abs(Controller.prevpinchlv - lvx) < Controller.pinch_threshold:
                    Controller.framecount += 1
                else:
                    Controller.prevpinchlv = lvx
                    Controller.framecount = 0

        def handle_controls(gesture, hand_result):  
            """Impliments all gesture functionality."""      
            x,y = None,None
            if gesture != Gest.PALM :
                x,y = Controller.get_position(hand_result)
            
            # flag reset
            if gesture != Gest.FIST and Controller.grabflag:
                Controller.grabflag = False
                pyautogui.mouseUp(button = "left")

            if gesture != Gest.PINCH_MAJOR and Controller.pinchmajorflag:
                Controller.pinchmajorflag = False

            if gesture != Gest.PINCH_MINOR and Controller.pinchminorflag:
                Controller.pinchminorflag = False

            # implementation
            if gesture == Gest.V_GEST:
                Controller.flag = True
                pyautogui.moveTo(x, y, duration = 0.1)

            elif gesture == Gest.FIST:
                if not Controller.grabflag : 
                    Controller.grabflag = True
                    pyautogui.mouseDown(button = "left")
                pyautogui.moveTo(x, y, duration = 0.1)

            elif gesture == Gest.MID and Controller.flag:
                pyautogui.click()
                Controller.flag = False

            elif gesture == Gest.INDEX and Controller.flag:
                pyautogui.click(button='right')
                Controller.flag = False

            elif gesture == Gest.TWO_FINGER_CLOSED and Controller.flag:
                pyautogui.doubleClick()
                Controller.flag = False

            elif gesture == Gest.PINCH_MINOR:
                if Controller.pinchminorflag == False:
                    Controller.pinch_control_init(hand_result)
                    Controller.pinchminorflag = True
                Controller.pinch_control(hand_result,Controller.scrollHorizontal, Controller.scrollVertical)
            
            elif gesture == Gest.PINCH_MAJOR:
                if Controller.pinchmajorflag == False:
                    Controller.pinch_control_init(hand_result)
                    Controller.pinchmajorflag = True
                Controller.pinch_control(hand_result,Controller.changesystembrightness, Controller.changesystemvolume)
            
    '''
    ----------------------------------------  Main Class  ----------------------------------------
        Entry point of Gesture Controller
    '''


    class GestureController:
        gc_mode = 0
        cap = None
        CAM_HEIGHT = None
        CAM_WIDTH = None
        hr_major = None # Right Hand by default
        hr_minor = None # Left hand by default
        dom_hand = True

        def __init__(self):
            """Initilaizes attributes."""
            GestureController.gc_mode = 1
            GestureController.cap = cv2.VideoCapture(0)
            GestureController.CAM_HEIGHT = GestureController.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            GestureController.CAM_WIDTH = GestureController.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        
        def classify_hands(results):
            left , right = None,None
            try:
                handedness_dict = MessageToDict(results.multi_handedness[0])
                if handedness_dict['classification'][0]['label'] == 'Right':
                    right = results.multi_hand_landmarks[0]
                else :
                    left = results.multi_hand_landmarks[0]
            except:
                pass

            try:
                handedness_dict = MessageToDict(results.multi_handedness[1])
                if handedness_dict['classification'][0]['label'] == 'Right':
                    right = results.multi_hand_landmarks[1]
                else :
                    left = results.multi_hand_landmarks[1]
            except:
                pass
            
            if GestureController.dom_hand == True:
                GestureController.hr_major = right
                GestureController.hr_minor = left
            else :
                GestureController.hr_major = left
                GestureController.hr_minor = right

        def start(self):
            
            handmajor = HandRecog(HLabel.MAJOR)
            handminor = HandRecog(HLabel.MINOR)

            with mp_hands.Hands(max_num_hands = 2,min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
                while GestureController.cap.isOpened() and GestureController.gc_mode:
                    success, image = GestureController.cap.read()

                    if not success:
                        print("Ignoring empty camera frame.")
                        continue
                    
                    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
                    image.flags.writeable = False
                    results = hands.process(image)
                    
                    image.flags.writeable = True
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                    if results.multi_hand_landmarks:                   
                        GestureController.classify_hands(results)
                        handmajor.update_hand_result(GestureController.hr_major)
                        handminor.update_hand_result(GestureController.hr_minor)

                        handmajor.set_finger_state()
                        handminor.set_finger_state()
                        gest_name = handminor.get_gesture()

                        if gest_name == Gest.PINCH_MINOR:
                            Controller.handle_controls(gest_name, handminor.hand_result)
                        else:
                            gest_name = handmajor.get_gesture()
                            Controller.handle_controls(gest_name, handmajor.hand_result)
                        
                        for hand_landmarks in results.multi_hand_landmarks:
                            mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    else:
                        Controller.prev_hand = None
                    cv2.imshow('Gesture Controller', image)
                    if cv2.waitKey(5) & 0xFF == ord("q"):
                        break
            GestureController.cap.release()
            cv2.destroyAllWindows()

    # uncomment to run directly
    gc1 = GestureController()
    gc1.start() 


def close():
    Break


def about_page():
    global current_frame

    if current_frame is not None:
        current_frame.destroy()

    if frame1 is not None:
        frame1.destroy()

    about_frame = customtkinter.CTkFrame(master=root)
    about_frame.pack(fill="both", expand=True)

    current_frame = about_frame

    about_label = customtkinter.CTkLabel(
        master=about_frame, text="About Page", font=("Barlow Medium", 40)
    )
    about_label.pack(pady=24, padx=20)

    home_button = customtkinter.CTkButton(
        master=about_frame,
        width=100,
        height=50,
        corner_radius=10,
        text="HOME",
        text_color="#000000",
        font=("Barlow medium", 18),
        command=go_to_home,
        fg_color="#868C92",
    )
    home_button.pack(pady=24, padx=20, anchor="ne")

    # Add other widgets and content for the about page

    # Example title
    about_content = customtkinter.CTkLabel(
        master=about_frame,
        text="MOVEMATE",
        font=("Barlow Regular", 16),
    )
    about_content.pack(pady=24, padx=20)
    about_content.place(relx=0.1, rely=0.1)

    # text one
    additional_text = customtkinter.CTkLabel(
        master=about_frame,
        text="1. palm: stable",
        font=("Barlow Regular", 16),
    )
    additional_text.pack(pady=24, padx=20)
    additional_text.place(relx=0.2, rely=0.2)

    # Add palm
    image_path = r"E:\Projects\Mini project\Movemate\Movemate\main\SS.jpg"
    image = ImageTk.PhotoImage(Image.open(image_path))
    image_label = tkinter.Label(about_frame, image=image)
    image_label.pack(pady=24, padx=20)
    image_label.place(relx=0.2, rely=0.3, relheight=0.4, relwidth=0.4)

    # Add right click
    image_path = r"E:\Projects\Mini project\Movemate\Movemate\main\SS.png"
    image = ImageTk.PhotoImage(Image.open(image_path))
    image_label = tkinter.Label(about_frame, image=image)
    image_label.pack(pady=24, padx=20)
    image_label.place(relx=0.4, rely=0.5, relheight=0.4, relwidth=0.2)

    # Add Move
    image_path = r"E:\Projects\Mini project\Movemate\Movemate\main\SS.png"
    image = ImageTk.PhotoImage(Image.open(image_path))
    image_label = tkinter.Label(about_frame, image=image)
    image_label.pack(pady=24, padx=20)
    image_label.place(relx=0.6, rely=0.7, relheight=0.4, relwidth=0.2)

    # Add more text
    additional_text = customtkinter.CTkLabel(
        master=about_frame,
        text="Additional information...",
        font=("Barlow Regular", 16),
    )
    additional_text.pack(pady=24, padx=20)

#ADD more information about it


def go_to_home():
    global current_frame

    side_bar = r"E:\Projects\Mini project\Movemate\Movemate\main\Side_Bar\SIDE_BAR.png"

    if current_frame is not None:
        current_frame.destroy()

    frame1 = customtkinter.CTkFrame(master=root)
    frame1.pack(fill="both", expand=True)

    current_frame = frame1
    
    image1 = Image.open(side_bar)
    photo1 = ImageTk.PhotoImage(image1)
    label2 = tkinter.Label(root, image=photo1)
    label2.pack(expand=True)
    label2.place(relx=0, rely=0.5, anchor=tkinter.W)

    label5 = customtkinter.CTkLabel(
        master=frame1, text="MOVEMATE", font=("ColorTube", 80)
    )
    label5.pack(pady=24, padx=20, expand=True)
    label5.place(relx=0.15, rely=0.15)

    label6 = customtkinter.CTkLabel(
        master=frame1, text="Gesture Controlled", font=("Baron Neue", 30)
    )
    label6.pack(pady=24, padx=20)
    label6.place(relx=0.15, rely=0.33)

    label7 = customtkinter.CTkLabel(
        master=frame1, text="Virtual Mouse", font=("Baron Neue", 30)
    )
    label7.pack(pady=24, padx=20)
    label7.place(relx=0.15, rely=0.38)

    button3 = customtkinter.CTkButton(
        master=frame1,
        width=100,
        height=50,
        corner_radius=10,
        text="HOME",
        text_color="#000000",
        font=("Barlow medium", 18),
        command=go_to_home,
        fg_color="#868C92",
    )
    button3.pack(pady=24, padx=20, expand=True)
    button3.place(relx=0.8, rely=0.02)

    button2 = customtkinter.CTkButton(
        master=frame1,
        width=100,
        height=50,
        corner_radius=10,
        text="ABOUT",
        text_color="#000000",
        font=("Barlow medium", 18),
        command=about_page,
        fg_color="#868C92",
    )
    button2.pack(pady=24, padx=20, expand=True)
    button2.place(relx=0.9, rely=0.02)

    button1 = customtkinter.CTkButton(
        master=frame1,
        width=290,
        height=65,
        corner_radius=47,
        text="START",
        text_color="#000000",
        font=("Barlow Semibold", 40),
        command=start,
        fg_color="#868C92",
    )
    button1.pack(pady=24, padx=20, expand=True)
    button1.place(relx=0.15, rely=0.65)

    label8 = customtkinter.CTkLabel(
        master=frame1,
        width=290,
        height=65,
        corner_radius=47,
        text="press 'q' to close tab",
        text_color="#000000",
        font=("Barlow Semibold", 20),
        fg_color="#868C92",
    )
    label8.pack(pady=24, padx=20, expand=True)
    label8.place(relx=0.15, rely=0.8)

side_bar = r"E:\Projects\Mini project\Movemate\Movemate\main\Side_Bar\SIDE_BAR.png"

frame1 = customtkinter.CTkFrame(master=root)
frame1.pack(fill="both", expand=True)

image1 = Image.open(side_bar)
photo1 = ImageTk.PhotoImage(image1)
label2 = tkinter.Label(root, image=photo1)
label2.pack(expand=True)
label2.place(relx=0, rely=0.5, anchor=tkinter.W)

label5 = customtkinter.CTkLabel(master=frame1, text="MOVEMATE", font=("ColorTube", 80))
label5.pack(pady=24, padx=20, expand=True)
label5.place(relx=0.15, rely=0.15)

label6 = customtkinter.CTkLabel(
    master=frame1, text="Gesture Controlled", font=("Baron Neue", 30)
)
label6.pack(pady=24, padx=20)
label6.place(relx=0.15, rely=0.33)

label7 = customtkinter.CTkLabel(
    master=frame1, text="Virtual Mouse", font=("Baron Neue", 30)
)
label7.pack(pady=24, padx=20)
label7.place(relx=0.15, rely=0.38)

button3 = customtkinter.CTkButton(
    master=frame1,
    width=100,
    height=50,
    corner_radius=10,
    text="HOME",
    text_color="#000000",
    font=("Barlow medium", 18),
    command=go_to_home,
    fg_color="#868C92",
)
button3.pack(pady=24, padx=20, expand=True)
button3.place(relx=0.8, rely=0.02)

button2 = customtkinter.CTkButton(
    master=frame1,
    width=100,
    height=50,
    corner_radius=10,
    text="ABOUT",
    text_color="#000000",
    font=("Barlow medium", 18),
    command=about_page,
    fg_color="#868C92",
)
button2.pack(pady=24, padx=20, expand=True)
button2.place(relx=0.9, rely=0.02)

button1 = customtkinter.CTkButton(
    master=frame1,
    width=290,
    height=65,
    corner_radius=47,
    text="START",
    text_color="#000000",
    font=("Barlow Semibold", 40),
    command=start,
    fg_color="#868C92",
)
button1.pack(pady=24, padx=20, expand=True)
button1.place(relx=0.15, rely=0.65)

label8 = customtkinter.CTkLabel(
    master=frame1,
    width=290,
    height=65,
    corner_radius=47,
    text="press 'q' to close tab",
    text_color="#000000",
    font=("Barlow Semibold", 20),
    fg_color="#868C92",
)
label8.pack(pady=24, padx=20, expand=True)
label8.place(relx=0.15, rely=0.8)

root.mainloop()