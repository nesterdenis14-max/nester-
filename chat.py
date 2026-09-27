# send_msg 50/50,, open_img, remove_img

from customtkinter import *
from PIL import Image, ImageDraw, ImageFont
import socket, threading, io, base64, os, hashlib
from tkinter import filedialog
from datetime import datetime


class SettingsWindow(CTkToplevel):
    def __init__(self, master, main_window):
        super().__init__(master)
        self.main_window = main_window
        self.title("Налаштування")
        self.geometry("400x450")
        self.resizable(False, False)
        
        # Робимо вікно модальним
        self.transient(master)
        self.grab_set()
        
        # Початкові значення
        self.new_avatar_raw = None
        self.new_avatar_image = None
        
        # Заголовок
        CTkLabel(
            self,
            text="Налаштування профілю",
            font=("Arial", 18, "bold")
        ).pack(pady=(20, 10))
        
        # --- Секція аватара ---
        avatar_frame = CTkFrame(self, fg_color="transparent")
        avatar_frame.pack(pady=10, padx=20, fill="x")
        
        CTkLabel(
            avatar_frame,
            text="Аватар:",
            font=("Arial", 13, "bold")
        ).pack(anchor="w")
        
        # Прев'ю аватара
        self.avatar_preview = CTkLabel(avatar_frame, text="")
        self.avatar_preview.pack(pady=10)
        self._update_avatar_preview()
        
        # Кнопки для аватара
        avatar_btn_frame = CTkFrame(avatar_frame, fg_color="transparent")
        avatar_btn_frame.pack(pady=5)
        
        CTkButton(
            avatar_btn_frame,
            text="Завантажити",
            command=self.load_avatar,
            width=120
        ).pack(side="left", padx=5)
        
        CTkButton(
            avatar_btn_frame,
            text="Скинути",
            command=self.reset_avatar,
            width=120,
            fg_color="#8B0000",
            hover_color="#5C0000"
        ).pack(side="left", padx=5)
        
        # --- Секція нікнейму ---
        CTkLabel(
            self,
            text="Нікнейм:",
            font=("Arial", 13, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))
        
        self.nickname_entry = CTkEntry(
            self,
            placeholder_text="Введіть новий нікнейм",
            width=300,
            height=35
        )
        self.nickname_entry.pack(padx=20)
        self.nickname_entry.insert(0, self.main_window.username)
        
        # --- Кнопки збереження ---
        btn_frame = CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=25)
        
        CTkButton(
            btn_frame,
            text="Зберегти",
            command=self.save_settings,
            width=120,
            fg_color="#2E8B57",
            hover_color="#1F5F3A"
        ).pack(side="left", padx=5)
        
        CTkButton(
            btn_frame,
            text="Скасувати",
            command=self.destroy,
            width=120,
            fg_color="#555555",
            hover_color="#333333"
        ).pack(side="left", padx=5)
    
    def _update_avatar_preview(self):
        """Оновлює прев'ю аватара у вікні налаштувань."""
        if self.new_avatar_image is not None:
            # Показуємо завантажену картинку
            preview = self.new_avatar_image.resize((100, 100), Image.Resampling.LANCZOS)
            ctk_img = CTkImage(preview, size=(100, 100))
            self.avatar_preview.configure(image=ctk_img, text="")
        else:
            # Показуємо поточний аватар
            current = self.main_window.get_avatar(self.main_window.username, size=100)
            self.avatar_preview.configure(image=current, text="")
    
    def load_avatar(self):
        """Завантажує нову картинку аватара."""
        file_name = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if not file_name:
            return
        try:
            with open(file_name, "rb") as f:
                self.new_avatar_raw = f.read()
            self.new_avatar_image = Image.open(file_name).convert("RGBA")
            self._update_avatar_preview()
        except Exception as e:
            print(f"Помилка завантаження аватара: {e}")
    
    def reset_avatar(self):
        """Скидає аватар до стандартного (згенерованого)."""
        self.new_avatar_raw = None
        self.new_avatar_image = None
        self._update_avatar_preview()
    
    def save_settings(self):
        """Зберігає всі зміни."""
        new_nickname = self.nickname_entry.get().strip()
        
        # Зберігаємо нікнейм
        if new_nickname and new_nickname != self.main_window.username:
            old_name = self.main_window.username
            self.main_window.username = new_nickname
            
            # Повідомляємо сервер про зміну імені
            try:
                msg = f"TEXT@{new_nickname}@[SYSTEM] {old_name} змінив ім'я на {new_nickname}\n"
                self.main_window.socket.sendall(msg.encode("utf-8"))
            except Exception:
                pass
        
        # Зберігаємо аватар
        if self.new_avatar_raw is not None:
            self.main_window.set_custom_avatar(self.new_avatar_raw, self.new_avatar_image)
        
        self.destroy()


class MainWindow(CTk):
    def __init__(self, username, server, port):
        super().__init__()
        self.geometry('500x450')  # Трохи вище, щоб вмістити кнопку налаштувань
        self.username = username

        # Кеш аватарів
        self._avatar_cache = {}
        
        # Кастомний аватар користувача (якщо завантажений)
        self._custom_avatar_raw = None
        self._custom_avatar_pil = None

        # --- Кнопка налаштувань зверху ---
        self.settings_btn = CTkButton(
            self,
            text="⚙ Налаштування",
            width=140,
            height=30,
            command=self.open_settings,
            fg_color="#444444",
            hover_color="#666666"
        )
        self.settings_btn.place(x=10, y=8)

        # Заголовок з іменем користувача
        self.user_label = CTkLabel(
            self,
            text=f"👤 {self.username}",
            font=("Arial", 12, "bold")
        )
        self.user_label.place(x=160, y=12)

        self.chat_field = CTkScrollableFrame(self)
        self.chat_field.place(x=0, y=45)  # Зсуваємо вниз через кнопку

        self.message_entry = CTkEntry(
            self,
            placeholder_text="Введіть ваше повідомлення",
            height=40
        )
        self.message_entry.place(x=0, y=0)

        self.message_entry.bind("<Return>", lambda event: self.send_msg())

        self.mgs_send_msg = CTkImage(
            light_image=Image.open("send.png"),
            size=(20, 20)
        )

        self.send_message = CTkButton(
            self,
            text="",
            image=self.mgs_send_msg,
            width=50,
            height=40,
            command=self.send_msg
        )
        self.send_message.place(x=0, y=0)

        self.img_send_img = CTkImage(
            light_image=Image.open("paper-clip.png"),
            size=(20, 20)
        )

        self.send_img = CTkButton(
            self,
            text="",
            image=self.img_send_img,
            width=50,
            height=40,
            command=self.open_img
        )
        self.send_img.place(x=0, y=0)

        self.adaptive_ui()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server, int(port)))
            hello = f"TEXT@{self.username}@[SYSTEM] {self.username} підключився до чату!\n"
            self.socket.sendall(hello.encode("utf-8"))
            threading.Thread(target=self.receive_message, daemon=True).start()
        except Exception as e:
            self.add_message(f"Не вдалось підключитися до сервера: {e}")

        self.raw = None
        self.file_name = None

        self.image_to_send = CTkLabel(self, text="")
        self.image_to_send.bind("<Button-1>", self.remove_img)

    def open_settings(self):
        """Відкриває вікно налаштувань."""
        SettingsWindow(self, self)

    def set_custom_avatar(self, raw_bytes, pil_image):
        """Встановлює кастомний аватар користувача."""
        self._custom_avatar_raw = raw_bytes
        self._custom_avatar_pil = pil_image
        # Очищаємо кеш для поточного користувача
        keys_to_remove = [k for k in self._avatar_cache if k[0] == self.username]
        for k in keys_to_remove:
            del self._avatar_cache[k]
        # Оновлюємо мітку користувача
        self.user_label.configure(text=f"👤 {self.username}")

    def adaptive_ui(self):
        self.send_message.place(
            x=self.winfo_width() // 1.25 - 50,
            y=self.winfo_height() // 1.25 - 40
        )
        self.send_img.place(
            x=self.winfo_width() // 1.25 - 105,
            y=self.winfo_height() // 1.25 - 40
        )
        self.message_entry.place(
            x=0,
            y=self.winfo_height() // 1.25 - 40
        )
        self.message_entry.configure(width=self.winfo_width() // 1.25 - 110)
        self.chat_field.configure(
            width=self.winfo_width() // 1.25 - 20,
            height=self.winfo_height() // 1.25 - 100  # Зменшено через кнопку зверху
        )
        self.after(100, self.adaptive_ui)

    def send_msg(self):
        message = self.message_entry.get()
        timestamp = datetime.now().strftime("%H:%M")

        if message and not self.raw:
            self.add_message(f"{self.username}: {message}", timestamp=timestamp, author=self.username)
            data = f"TEXT@{self.username}@{message}@{timestamp}\n"
            try:
                self.socket.sendall(data.encode())
            except:
                pass

        elif self.raw:
            b64_data = base64.b64encode(self.raw).decode()
            data = f"IMAGE@{self.username}@{message}@{b64_data}@{timestamp}\n"
            try:
                self.socket.sendall(data.encode())
            except:
                pass

            self.add_message(
                f"{self.username}: {message}",
                image=self.resize_img(Image.open(self.file_name)),
                timestamp=timestamp,
                author=self.username
            )
            self.remove_img()

        self.message_entry.delete(0, 'end')

    def create_avatar(self, username, size=40):
        """Створює круглий аватар з першою літерою імені та випадковим кольором."""
        # Якщо це наш користувач і у нього є кастомний аватар — використовуємо його
        if username == self.username and self._custom_avatar_pil is not None:
            img = self._custom_avatar_pil.copy()
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Робимо круглу маску
            mask = Image.new("L", (size, size), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, size - 1, size - 1), fill=255)
            
            # Застосовуємо маску
            result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            result.paste(img, (0, 0), mask)
            return result
        
        hash_val = int(hashlib.md5(username.encode("utf-8")).hexdigest(), 16)

        r = (hash_val & 0xFF0000) >> 16
        g = (hash_val & 0x00FF00) >> 8
        b = hash_val & 0x0000FF

        r = (r + 80) % 156 + 100
        g = (g + 80) % 156 + 100
        b = (b + 80) % 156 + 100

        color = (r, g, b)

        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.ellipse((0, 0, size - 1, size - 1), fill=color)

        letter = username[0].upper() if username else "?"

        try:
            font = ImageFont.truetype("arial.ttf", int(size * 0.55))
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.55))
            except Exception:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), letter, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (size - text_w) / 2 - bbox[0]
        text_y = (size - text_h) / 2 - bbox[1]

        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = (0, 0, 0, 255) if brightness > 180 else (255, 255, 255, 255)

        draw.text((text_x, text_y), letter, fill=text_color, font=font)

        return img

    def get_avatar(self, username, size=40):
        """Повертає CTkImage аватара з кешу."""
        key = (username, size)
        if key not in self._avatar_cache:
            pil_img = self.create_avatar(username, size)
            self._avatar_cache[key] = CTkImage(pil_img, size=(size, size))
        return self._avatar_cache[key]

    def add_message(self, message, image=None, timestamp=None, author=None):
        if author is None and ":" in message:
            author = message.split(":", 1)[0].strip()
        if author is None:
            author = self.username

        message_frame = CTkFrame(self.chat_field, fg_color="#636363")
        message_frame.pack(pady=5, anchor="w")

        row = CTkFrame(message_frame, fg_color="transparent")
        row.pack(padx=10, pady=(5, 0), anchor="w", fill="x")

        avatar = self.get_avatar(author, size=40)
        CTkLabel(row, text="", image=avatar).pack(side="left", padx=(0, 8), anchor="n")

        content = CTkFrame(row, fg_color="transparent")
        content.pack(side="left", fill="x", expand=True)

        wrap = self.winfo_width() - 100
        if wrap < 100:
            wrap = 300

        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M")

        if not image:
            CTkLabel(
                content,
                text=message,
                wraplength=wrap,
                justify="left",
                text_color="white"
            ).pack(anchor="w")
        else:
            CTkLabel(
                content,
                text=message,
                wraplength=wrap,
                justify="left",
                image=image,
                compound='top',
                text_color="white"
            ).pack(anchor="w")

        CTkLabel(
            content,
            text=timestamp,
            font=("Arial", 9),
            text_color="#b0b0b0",
        ).pack(anchor="w")

        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self.chat_field.update_idletasks()
        try:
            self.chat_field._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def receive_message(self):
        buffer = ""
        while True:
            try:
                message = self.socket.recv(16384)
                buffer += message.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    print(f"LINE: {line}")
                    self.handle_line(line.strip())
            except:
                break
        self.socket.close()

    def handle_line(self, line):
        if not line:
            return

        parts = line.split("@", 3)
        msg_type = parts[0]

        if msg_type == "TEXT":
            timestamp = parts[3] if len(parts) > 3 else None
            self.add_message(
                f'{parts[1]}: {parts[2]}',
                timestamp=timestamp,
                author=parts[1]
            )

        elif msg_type == "IMAGE":
            try:
                payload = parts[3].split("@", 1)
                b64_data = payload[0]
                timestamp = payload[1] if len(payload) > 1 else None

                image_data = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(image_data))
                img = self.resize_img(img)
                self.add_message(
                    f"{parts[1]}: {parts[2]}",
                    image=img,
                    timestamp=timestamp,
                    author=parts[1]
                )
            except Exception as e:
                self.add_message(f"Помилка: {e}")

    def resize_img(self, image):
        width, height = image.size
        max_height = 400
        max_width = 400

        if width < max_width:
            if height < max_height:
                return CTkImage(image, size=(width, height))
            else:
                max_width = int((max_height * width) / height)

        max_height = int((max_width * height) / width)
        resized_img = image.resize((max_width, max_height), Image.Resampling.LANCZOS)
        return CTkImage(resized_img, size=(max_width, max_height))

    def open_img(self):
        self.file_name = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if not self.file_name:
            return
        try:
            with open(self.file_name, "rb") as f:
                self.raw = f.read()
                img = Image.open(self.file_name)
                img = img.resize((100, 100), Image.Resampling.LANCZOS)
                preview_img = CTkImage(img, size=(100, 100))
                self.image_to_send.configure(image=preview_img, text="")
                self.image_to_send.place(
                    x=10,
                    y=self.winfo_height() // 1.25 - 150
                )
        except Exception as e:
            self.add_message(f"Помилка {e}")

    def remove_img(self, e=None):
        self.image_to_send.place_forget()
        self.raw = None
        self.file_name = None