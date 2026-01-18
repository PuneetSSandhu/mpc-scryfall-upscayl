import tkinter as tk
from tkinter import filedialog, messagebox


class TextEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Text Editor")
        self.file_path = None

        # Text widget
        self.text = tk.Text(root, wrap="word", undo=True)
        self.text.pack(expand=True, fill="both")

        # Menu bar
        menu = tk.Menu(root)
        root.config(menu=menu)

        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.text.delete("1.0", tk.END)
                self.text.insert(tk.END, f.read())
            self.file_path = path
            self.root.title(f"Simple Text Editor — {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{e}")

    def save_file(self):
        if not self.file_path:
            self.save_file_as()
            return
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", tk.END))
            messagebox.showinfo("Saved", "File saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return
        self.file_path = path
        self.save_file()


if __name__ == "__main__":
    root = tk.Tk()
    app = TextEditor(root)
    root.mainloop()
