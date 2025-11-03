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
pip install git+https://github.com/thisirs/guv.git
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

2. **Provide a base listing file**:

    Place the csv/Excel file of a listing of students under some directory, for
    example `Fall2024/CS042/documents` and declare it in
    `Fall2024/CS042/config.py` like this:

    ```python
    DOCS = Documents()
    DOCS.add("documents/base_listing.xlsx")
    ```

    Now go to `CS042` subdirectory and run `guv` without arguments. The result
    is in a file called `effectif.xlsx` under `Fall2024/CS042`.

    Depending on the column names of your listing, you might need to update
    the column mappings in the `config.py` file located in `Fall2024`.

3. **Use tasks to generate files**

    If `CS042` directory, you can now generate attendance sheets:

    ```shell
    guv pdf_attendance --title "Exam"
    ```

    or generate a gradebook (you will be asked for a marking scheme):

    ```shell
    guv xls_gradebook_no_group --name Exam1
    ```

    See other tasks [here](tasks.rst).

4. **Aggregate more files to the base listing**

    If you want to add more information to the base listing:

    ```python
    DOCS = Documents()
    DOCS.add("documents/base_listing.xlsx")
    DOCS.aggregate("documents/grades.xlsx", on="Email")
    ```

    and see the result in `effectif.xlsx` under `Fall2024/CS042`.

    See other aggregating functions [here](operations.rst).

See all available tasks and aggregating functions [here](https://thisirs.github.io/guv/).
