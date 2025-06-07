Send an email to each student.

The only required argument is a path to a file used as the email template.
If the file does not exist, a default template is created. The template
follows the Jinja2 format, and the available replacement variables for
each student correspond to the column names in the ``effectif.xlsx`` file.

To enable email sending, you must set the ``LOGIN`` (SMTP server login),
``FROM_EMAIL`` (sender email address), ``SMTP_SERVER`` and ``PORT``
(default: 587) variables in the ``config.py`` file.

{options}

Examples
--------

.. code:: bash

   guv send_email documents/email_body

with ``documents/email_body`` containing:

.. code:: text

   Subject: Note

   Hello {{ Name }},

   You are part of the group {{ group_project }}.

   Cheers,

   guv
