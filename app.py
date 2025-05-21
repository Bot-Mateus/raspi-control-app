#!/usr/bin/env python3
import os
import subprocess
import shutil
import shlex
from datetime import datetime

import psutil
from flask import (
    Flask, request, send_from_directory, render_template,
    redirect, url_for, abort, Response, stream_with_context,
    session, flash
)
from pam import pam
from functools import wraps

# --- INICIALIZAÇÃO ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = '123456'

# --- AUTENTICAÇÃO ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd  = request.form['password']
        if pam().authenticate(user, pwd):
            session['user'] = user
            nxt = request.args.get('next') or url_for('index')
            return redirect(nxt)
        else:
            flash('Credenciais inválidas', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- CONSTANTES ---
SSD_PATH      = '/mnt/ssd'
FILE_ROOT     = os.path.expanduser('~')
CAMERA_RES    = '640x480'
CAMERA_FPS    = '15'
INPUT_PLUGIN  = 'input_uvc.so'
OUTPUT_PLUGIN = 'output_http.so'
WWW_DIR       = '/usr/local/share/mjpg-streamer/www'
MJPG_PORT     = '8080'

# --- FUNÇÃO DE STREAMING ---
def is_streaming():
    return subprocess.call(
        ['pgrep','-f','mjpg_streamer'], stdout=subprocess.DEVNULL
    ) == 0

@app.route('/')
@login_required
def index():
    du = shutil.disk_usage('/')
    root_stats = {'label':'Root','total':du.total,'used':du.used,'free':du.free}
    if os.path.isdir(SSD_PATH):
        du2 = shutil.disk_usage(SSD_PATH)
        ssd_stats = {'label':'SSD','total':du2.total,'used':du2.used,'free':du2.free}
        ssd_connected = True
    else:
        ssd_stats = None
        ssd_connected = False
    mem = psutil.virtual_memory()
    ram_stats = {'label':'RAM','total':mem.total,'used':mem.used,'free':mem.available}
    files = sorted(f for f in os.listdir(SSD_PATH) if f.lower().endswith(('.mp4','.mov','.mkv','.avi'))) if ssd_connected else []
    return render_template('index.html', root_stats=root_stats, ssd_stats=ssd_stats,
                           ram_stats=ram_stats, files=files, ssd_connected=ssd_connected,
                           streaming=is_streaming(), host=request.host.split(':')[0], port=MJPG_PORT,
                           clipboard=session.get('clipboard'))

@app.route('/camera/<action>')
@login_required
def camera(action):
    subprocess.call(['pkill','mjpg_streamer'])
    if action=='start':
        subprocess.Popen([
            'mjpg_streamer',
            '-i', f"{INPUT_PLUGIN} -r {CAMERA_RES} -f {CAMERA_FPS}",
            '-o', f"{OUTPUT_PLUGIN} -w {WWW_DIR} -p {MJPG_PORT}"
        ])
    return redirect(url_for('index'))

@app.route('/videos/download/<path:filename>')
@login_required
def download_video(filename):
    if not os.path.isdir(SSD_PATH): abort(404)
    return send_from_directory(SSD_PATH, filename, as_attachment=True)

@app.route('/videos/upload', methods=['POST'])
@login_required
def upload_video():
    if not os.path.isdir(SSD_PATH): abort(400)
    f = request.files.get('file')
    dest = os.path.join(SSD_PATH, f.filename)
    f.save(dest)
    return redirect(url_for('index'))

@app.route('/files/', defaults={'req_path':''})
@app.route('/files/<path:req_path>')
@login_required
def browse(req_path):
    abs_path = os.path.normpath(os.path.join(FILE_ROOT, req_path))
    if not abs_path.startswith(FILE_ROOT): abort(403)
    if os.path.isdir(abs_path):
        items=[]
        parent=os.path.relpath(os.path.dirname(abs_path), FILE_ROOT)
        if abs_path!=FILE_ROOT: items.append({'name':'..','path':parent,'is_dir':True,'size':0,'mtime':''})
        for name in sorted(os.listdir(abs_path)):
            full=os.path.join(abs_path, name)
            rel=os.path.relpath(full, FILE_ROOT)
            stat=os.stat(full)
            items.append({'name':name,'path':rel,'is_dir':os.path.isdir(full),
                          'size':stat.st_size,
                          'mtime':datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')})
        return render_template('files.html', items=items, cur_path=os.path.relpath(abs_path,FILE_ROOT), clipboard=session.get('clipboard'))
    elif os.path.isfile(abs_path):
        content=open(abs_path,'r',encoding='utf-8',errors='ignore').read()
        rel=os.path.relpath(abs_path, FILE_ROOT)
        parent=os.path.dirname(rel)
        return render_template('edit.html', file_path=rel, content=content, parent_path=parent)
    else:
        abort(404)

@app.route('/files/create', methods=['POST'])
@login_required
def create():
    cur=request.form.get('current_path','')
    name=request.form.get('new_name')
    typ=request.form.get('new_type')
    abs_c=os.path.normpath(os.path.join(FILE_ROOT,cur))
    tgt=os.path.join(abs_c,name)
    if typ=='dir': os.makedirs(tgt, exist_ok=True)
    else: open(tgt,'w').close()
    return redirect(url_for('browse', req_path=cur))

@app.route('/files/delete/<path:req_path>', methods=['POST'])
@login_required
def delete(req_path):
    abs_p=os.path.normpath(os.path.join(FILE_ROOT, req_path))
    if os.path.isdir(abs_p): shutil.rmtree(abs_p)
    else: os.remove(abs_p)
    return redirect(url_for('browse', req_path=os.path.dirname(req_path)))

@app.route('/files/rename', methods=['POST'])
@login_required
def rename():
    src=request.form['path']; new=request.form['new_name']
    abs_old=os.path.normpath(os.path.join(FILE_ROOT,src))
    abs_new=os.path.join(os.path.dirname(abs_old), new)
    os.rename(abs_old, abs_new)
    return redirect(url_for('browse', req_path=os.path.dirname(src)))

@app.route('/files/copy', methods=['POST'])
@login_required
def copy_item():
    session['clipboard']={'action':'copy','path':request.form['path']}
    return redirect(url_for('browse', req_path=''))

@app.route('/files/move', methods=['POST'])
@login_required
def move_item():
    session['clipboard']={'action':'move','path':request.form['path']}
    return redirect(url_for('browse', req_path=''))

@app.route('/files/cancel')
@login_required
def cancel_clipboard():
    session.pop('clipboard', None)
    return redirect(url_for('browse', req_path=''))

@app.route('/files/paste', methods=['POST'])
@login_required
def paste_item():
    clip=session.get('clipboard')
    tgt=request.form['target_path']
    abs_src=os.path.normpath(os.path.join(FILE_ROOT, clip['path']))
    abs_dst_dir=os.path.normpath(os.path.join(FILE_ROOT, tgt))
    name=os.path.basename(clip['path'])
    abs_dst=os.path.join(abs_dst_dir, name)
    if clip['action']=='copy':
        shutil.copy2(abs_src,abs_dst) if os.path.isfile(abs_src) else shutil.copytree(abs_src,abs_dst)
    else:
        os.rename(abs_src,abs_dst)
    session.pop('clipboard')
    return redirect(url_for('browse', req_path=tgt))

@app.route('/files/download_folder/<path:req_path>')
@login_required
def download_folder(req_path):
    abs_p=os.path.normpath(os.path.join(FILE_ROOT, req_path))
    archive=f"{os.path.basename(req_path) or 'home'}.tar"  
    proc=subprocess.Popen(shlex.split(f"tar -C {shlex.quote(FILE_ROOT)} -cf - {shlex.quote(req_path)}"), stdout=subprocess.PIPE)
    return Response(stream_with_context(proc.stdout), mimetype='application/x-tar', headers={ 'Content-Disposition': f'attachment; filename="{archive}"' })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
