# Tech Daily Newsletter

Boletin diario de noticias tecnicas enviado automaticamente a Telegram.

## Como funciona

GitHub Actions ejecuta `src/send_newsletter.py` una vez al dia y envia el mensaje al chat configurado en los secrets del repositorio.

- Horario: diario
- Se dispara en: `workflows/tech-news-daily.yml`
- Script: `src/send_newsletter.py`

## Secrets requeridos

Crear en GitHub > Settings > Secrets and variables > Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Prueba local

```bash
cd ~/telegram-newsletter
python3 -m venv .venv
. .venv/bin/activate
pip install -r src/requirements.txt
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_CHAT_ID='...'
python3 src/send_newsletter.py
```

Si devuelve `{"ok": true, ...}` el envio se realizo.

## Ejecutar desde GitHub

1. Ir a `Actions` > `Tech Daily Newsletter`
2. `Run workflow`
3. Elegir la rama y ejecutar

No hace falta dejar la pestaña abierta; el workflow se ejecuta en GitHub.


