# Shell Completion

`guv` provides shell completion scripts for both Bash and Zsh, with support for multiple languages (English and French).

## What is Shell Completion?

Shell completion allows you to use the Tab key to:
- Complete command names
- Complete task names
- Complete option names
- Get file suggestions for file-based options
- See available column names for column-based options

## Available Completion Scripts

The following completion scripts are included with `guv`:

- `_guv_bash_en` - Bash completion (English)
- `_guv_bash_fr` - Bash completion (French)
- `_guv_zsh_en` - Zsh completion (English)
- `_guv_zsh_fr` - Zsh completion (French)

These files are located in `src/guv/data/` within the installation directory.

## Installation

### Finding the Completion Scripts

First, find where `guv` is installed:

```bash
# Find the guv installation directory
python -c "import guv; import os; print(os.path.dirname(guv.__file__))"
```

The completion scripts will be in the `data/` subdirectory of this path.

### Zsh Installation

#### User-specific Installation (Recommended)

Add to your `~/.zshrc`:

```bash
# For English
source /path/to/guv/src/guv/data/_guv_zsh_en

# For French
source /path/to/guv/src/guv/data/_guv_zsh_fr
```

Then reload your shell:

```bash
source ~/.zshrc
```

#### System-wide Installation

For all users on the system:

```bash
# Copy to system completion directory
sudo cp /path/to/guv/src/guv/data/_guv_zsh_en /usr/share/zsh/site-functions/_guv

# Or for Oh My Zsh users
cp /path/to/guv/src/guv/data/_guv_zsh_en ~/.oh-my-zsh/completions/_guv
```

### Bash Installation

#### User-specific Installation (Recommended)

Add to your `~/.bashrc`:

```bash
# For English
source /path/to/guv/src/guv/data/_guv_bash_en

# For French
source /path/to/guv/src/guv/data/_guv_bash_fr
```

Then reload your shell:

```bash
source ~/.bashrc
```

#### System-wide Installation

For all users on the system:

```bash
# Debian/Ubuntu
sudo cp /path/to/guv/src/guv/data/_guv_bash_en /etc/bash_completion.d/guv

# RHEL/CentOS/Fedora
sudo cp /path/to/guv/src/guv/data/_guv_bash_en /etc/bash_completion.d/guv

# macOS (with Homebrew bash-completion)
cp /path/to/guv/src/guv/data/_guv_bash_en /usr/local/etc/bash_completion.d/guv
```

## Usage Examples

Once installed, you can use Tab completion in various ways:

### Complete Task Names

```bash
$ guv pdf_<TAB>
pdf_attendance       pdf_attendance_full

$ guv xls_<TAB>
xls_grade_book_group    xls_grade_book_no_group    xls_grade_book_jury
xls_student_data
```

### Complete Option Names

```bash
$ guv pdf_attendance --<TAB>
--blank           --group           --names           --save-tex
--count           --help            --latex-template  --tiers-temps
--extra           --title
```

### File Completion

For options that expect file paths (like `--latex-template`), Tab will show files:

```bash
$ guv pdf_attendance --latex-template <TAB>
attendance.tex.jinja2    custom_template.tex    my_template.tex.jinja2

$ guv pdf_attendance --latex-template ./templates/<TAB>
./templates/attendance_custom.tex    ./templates/attendance_modern.tex
```

### Column Completion

For options that expect column names (like `--group`), Tab will show available columns from `effectif.xlsx`:

```bash
$ guv pdf_attendance --group <TAB>
Tutorial    Practical work    Lecture    Project Group
```

:::{note}
Column completion only works when you're in a directory with `generated/.columns.list` file,
which is automatically created when you run tasks that process `effectif.xlsx`.
:::
