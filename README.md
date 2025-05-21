# Control App - Raspberry Pi 3

Este projeto transforma sua Raspberry Pi 3 em um servidor doméstico multifuncional, com:

1. **Servidor de arquivos e backup**  
   - SSD (ou pendrive/HD) portátil formatado em exFAT ou ext4, montado em `/mnt/ssd`.  
   - Armazena vídeos 4K e fotos, lidos/escritos por Windows, macOS, Linux e Android.

2. **Servidor de mídia on-demand**  
   - Câmera USB exposta via **MJPG-Streamer**.  
   - Streaming somente quando você clicar em “Ligar câmera”, economizando CPU e I/O.

3. **Aplicação web em Flask**  
   - Interface moderna, responsiva e mobile-first para:  
     - Ligar/Desligar câmera (`/camera/start`, `/camera/stop`)  
     - Visualizar stream embutido (`<img>` apontando para MJPG-Streamer).  
     - Listar e baixar vídeos do SSD (`/videos/download/<nome>`).  
     - Upload de vídeos para o SSD (`/videos/upload`).  
     - Navegador de arquivos (`/files/`):  
       - **Listagem** de diretórios e arquivos na home do usuário.  
       - **Edição inline** de arquivos de texto (`/files/<arquivo>`).  
       - **Criação** de novos arquivos ou pastas.  
       - **Exclusão** segura de arquivos ou pastas.

## Estrutura de arquivos
```
control-app/
├─ app.py             # código principal Flask com rotas de controle, upload, stream e file manager
├─ requirements.txt   # Flask==2.3.2
├─ venv/              # ambiente virtual Python 3
├─ static/
│  └─ style.css       # estilos globais e de editor
└─ templates/
   ├─ index.html      # página principal de controle de câmera e vídeos
   ├─ files.html      # listagem, criação e exclusão de arquivos/pastas
   └─ edit.html       # editor de texto full-screen com toolbar responsiva
```

## Novas Funcionalidades (File Manager)
- **Rotas**  
  - `GET /files/` e `GET /files/<path>`: navega e lista conteúdo de `~/`  
  - `POST /files/create`: cria arquivo ou pasta no diretório atual  
  - `POST /files/delete/<path>`: exclui arquivo ou pasta (recursivamente)  
  - `GET /files/<path>`: abre editor de texto para arquivos  
  - `POST /files/edit/<path>`: salva alterações no arquivo editado

- **Interface**  
  - Formulário no topo para criar novo **arquivo** ou **pasta**.  
  - Botão **Excluir** ao lado de cada item, com confirmação.  
  - Editor integrado com botões “Salvar” e “Cancelar”, cabeçalho e rodapé fixos.

## Serviço systemd
Arquivo: `/etc/systemd/system/control-app.service`  
- Auto-start no boot  
- Executa o Flask via `venv/bin/flask run --host=0.0.0.0 --port=8000`  
- Usuário: `mateus` (ajuste conforme seu usuário)  
- Reinício automático em falhas

## Configurações em `app.py`
- `SSD_PATH = "/mnt/ssd"`  
- `FILE_ROOT = os.path.expanduser("~")`  
- Parâmetros de câmera:  
  - Resolução: `CAMERA_RES = "640x480"`  
  - FPS:        `CAMERA_FPS = "15"`  
  - Porta MJPG: `MJPG_PORT = "8080"`
- Plugins MJPG: `input_uvc.so`, `output_http.so`  
- Diretório web MJPG: `/usr/local/share/mjpg-streamer/www`

## Fluxo de uso
1. **Conectar SSD/pendrive/HD** → montar em `/mnt/ssd`.  
2. Acessar `http://<IP-da-Pi>:8000/` via Tailscale ou LAN.  
3. Controlar câmera e visualizar stream.  
4. Listar, baixar e enviar vídeos no SSD.  
5. Navegar, criar, editar e excluir arquivos da sua home em `/files/`.

---