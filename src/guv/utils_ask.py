from fractions import Fraction
from prompt_toolkit.validation import Validator
from prompt_toolkit import prompt
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.widgets import Label, CheckboxList
from prompt_toolkit.layout.containers import HSplit

from .translations import _


def checkboxlist_prompt(
    title,
    values,
    default=None,
    cancel_value=None,
    style=None,
    async_=False,
):
    # Create the radio list
    checkbox_list = CheckboxList(values=values)
    # Remove the enter key binding so that we can augment it
    checkbox_list.control.key_bindings.remove("enter")

    bindings = KeyBindings()

    # Replace the enter key binding to select the value and also submit it
    @bindings.add("enter")
    def exit_with_value(event):
        """
        Pressing Enter will exit the user interface, returning the highlighted value.
        """
        # checkbox_list._handle_enter()
        event.app.exit(result=checkbox_list.current_values)

    @bindings.add("c-c")
    def backup_exit_with_value(event):
        """
        Pressing Ctrl-C will exit the user interface with the cancel_value.
        """
        event.app.exit(result=cancel_value)

    # Create and run the mini inline application
    application = Application(
        layout=Layout(HSplit([Label(title), checkbox_list])),
        key_bindings=merge_key_bindings([load_key_bindings(), bindings]),
        mouse_support=True,
        style=style,
        full_screen=False,
    )
    if async_:
        return application.run_async()
    else:
        return application.run()


def is_number(text):
    try:
        Fraction(text)
        return True
    except ValueError:
        return False


def prompt_number(message, **kwargs):
    validator = Validator.from_callable(
        is_number,
        error_message=_("Number or fraction not recognized"),
        move_cursor_to_end=True)
    number = float(Fraction(prompt(message, validator=validator, **kwargs)))
    return int(number) if number.is_integer() else number
