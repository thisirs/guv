# `guv`

**`guv`** is a command-line tool designed to simplify the management of multiple
courses. It helps centralize information related to each courses and easily
integrate new data through configuration files. With `guv`, you can generate,
attendance sheets, grade and jury spreadsheets, and much more!

---

## ✨ Features

- Centralized management courses information
- Excel grade sheets for courses assessment boards
- Easy customization via configuration files

---

## 🚀 Installation

Install `guv` directly via `pip`:

```shell
pip install https://github.com/thisirs/guv.git
```

---

## 🏃 Quick Start

Follow the steps below to get started with `guv`:

1. **Create a semester structure with some courses**:

    ```shell
    guv createsemester Fall2024 --uv CS042 CS314
    ```

    This creates a semester directory `Fall2024` containing to courses `CS314`
    and `CS042`.

2. **Provide a base listing file and add it in `config.py`**.

    Place the csv/Excel file of a listing of students under
    `Fall2024/CS042/documents` and tell `guv` to add it in
    `Fall2024/CS042/config.py`:

    ```python
    DOCS = Documents()
    DOCS.add("documents/base_listing.xlsx")
    ```

3. **Use tasks**

    Now go to `CS314` subdirectory:

    ```shell
    cd Fall2024/CS042
    ```

    You can now generate attendance sheets:

    ```shell
    guv pdf_attendance --title "Exam"
    ```

    Generate a gradebook (you will be asked for a marking scheme):

    ```shell
    guv xls_gradebook_no_group --name Exam1
    ```
