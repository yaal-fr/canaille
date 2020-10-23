Extract the messages with:

```
pybabel extract --mapping-file canaille/translations/babel.cfg --output-file canaille/translations/messages.pot .
```

Add a new language with:

```
pybabel init --input-file messages.pot --output-dir translations --locale <LANG>
```

Update the catalogs with:

```
pybabel update --input-file canaille/translations/messages.pot --output-dir canaille/translations
```

Compile the catalogs with:

```
pybabel compile --directory canaille/translations
```