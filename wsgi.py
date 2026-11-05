import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # En macOS el puerto 5000 lo ocupa AirPlay Receiver; por eso el valor por defecto es 5050.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
