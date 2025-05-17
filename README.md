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
    cd Fall2024
    ```

2. **Provide a base listing file and add it in `config.py`**.

    ```shell
    cd CS042
    edit config.py
    ```

    ```python
    DOCS.add("documents/base_listing.xlsx")
    ```

3. **Use tasks**

    Generate a gradebook

    ```shell
    guv xls_gradebook
    ```

    Generate attendance sheets

    ```shell
    guv pdf_attendance --title "Exam"
    ```
