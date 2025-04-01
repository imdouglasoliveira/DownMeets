"""
Script para baixar vídeos do Google Meet compartilhados no Google Drive.
Baseado nas técnicas do artigo: 
https://dev.to/gabrieldiem/how-to-download-google-meet-meeting-recordings-set-to-view-only-mode-4d2a
"""

import re
import os
import sys
import time
import subprocess
from pathlib import Path

# Garantir que as dependências necessárias estão instaladas
required_packages = ["yt-dlp", "requests", "tqdm", "gdown"]
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Instalando {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import requests
from tqdm import tqdm
import yt_dlp
import gdown

# Configurações
URL_FILE = "urls.txt"  # Arquivo com as URLs
OUTPUT_DIR = "meets"   # Diretório de saída
DELAY_MINUTES = 5      # Atraso entre downloads em minutos

def extract_file_id(url):
    """Extrai o ID do arquivo do Google Drive a partir da URL."""
    pattern = r'/d/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    else:
        raise ValueError("Não foi possível extrair o ID do arquivo da URL fornecida.")

def ensure_directory_exists(directory):
    """Garante que o diretório exista, criando-o se necessário."""
    Path(directory).mkdir(parents=True, exist_ok=True)

def generate_filename(file_id, index=None, extension="mp4"):
    """Gera um nome de arquivo baseado no ID e índice."""
    if index is not None:
        return f"meet_{index:03d}_{file_id[-6:]}.{extension}"
    return f"meet_{file_id[-6:]}.{extension}"

def wait_between_downloads(minutes=DELAY_MINUTES):
    """Aguarda um tempo específico entre downloads."""
    print(f"Aguardando {minutes} minuto(s) antes do próximo download...")
    time.sleep(minutes * 60)

def download_with_ytdlp(url, output_path):
    """Baixa vídeo usando yt-dlp."""
    print(f"Tentando baixar com yt-dlp: {url}")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Verificar se o arquivo foi baixado e tem tamanho
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            print("Arquivo baixado com yt-dlp está vazio ou não existe")
            return False
    except Exception as e:
        print(f"Erro com yt-dlp: {e}")
        return False

def download_with_requests(url, output_path):
    """Tenta baixar usando requests."""
    print(f"Tentando baixar com requests: {url}")
    
    try:
        # Extrair ID
        file_id = extract_file_id(url)
        
        # URL para download direto
        direct_url = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        # Cabeçalhos para emular navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://drive.google.com/',
        }
        
        # Sessão para manter cookies
        session = requests.Session()
        
        # Primeira requisição para obter cookies
        response = session.get(direct_url, headers=headers, stream=True)
        
        # Lidar com página de confirmação
        if 'confirm=' in response.url or 'confirm=' in response.text:
            confirm_match = re.search(r'confirm=([0-9A-Za-z_-]+)', response.url)
            if not confirm_match:
                confirm_match = re.search(r'confirm=([0-9A-Za-z_-]+)', response.text)
            
            if confirm_match:
                confirm_token = confirm_match.group(1)
                direct_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={confirm_token}"
                response = session.get(direct_url, headers=headers, stream=True)
        
        # Verificar se recebemos um arquivo ou HTML
        if 'text/html' in response.headers.get('Content-Type', ''):
            # Tentar extrair URL de mídia direta
            media_urls = re.findall(r'https://.*?googleusercontent\.com/[^"\'&?]+', response.text)
            media_urls = [u for u in media_urls if 'videoplayback' in u or 'media' in u]
            
            if media_urls:
                print(f"URL de mídia encontrada: {media_urls[0]}")
                response = session.get(media_urls[0], headers=headers, stream=True)
            else:
                return False
        
        # Obter tamanho do arquivo
        file_size = int(response.headers.get('content-length', 0))
        
        if file_size > 0:
            # Exibir progresso
            progress = tqdm(
                response.iter_content(1024),
                f"Baixando {os.path.basename(output_path)}",
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )
            
            # Baixar o arquivo
            with open(output_path, 'wb') as f:
                for data in progress.iterable:
                    f.write(data)
                    progress.update(len(data))
        else:
            # Sem content-length, baixar sem progresso
            with open(output_path, 'wb') as f:
                f.write(response.content)
        
        # Verificar se o arquivo baixado tem conteúdo
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            print("Arquivo baixado está vazio")
            return False
    
    except Exception as e:
        print(f"Erro com requests: {e}")
        return False

def download_with_gdown(url, output_path):
    """Tenta baixar usando gdown."""
    print(f"Tentando baixar com gdown: {url}")
    
    try:
        # Extrair ID
        file_id = extract_file_id(url)
        
        # Baixar com gdown
        gdown.download(id=file_id, output=output_path, quiet=False, fuzzy=True)
        
        # Verificar se o arquivo foi baixado com sucesso
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            print("gdown não conseguiu baixar o arquivo ou o arquivo está vazio")
            return False
    except Exception as e:
        print(f"Erro com gdown: {e}")
        return False

def download_meet_video(url, output_dir=OUTPUT_DIR, index=None):
    """Baixa um vídeo do Google Meet usando múltiplos métodos."""
    # Garantir que o diretório existe
    ensure_directory_exists(output_dir)
    
    # Extrair ID
    try:
        file_id = extract_file_id(url)
    except ValueError as e:
        print(f"Erro: {e}")
        return None
    
    # Definir caminho de saída
    filename = generate_filename(file_id, index)
    output_path = os.path.join(output_dir, filename)
    print(f"Baixando para: {output_path}")
    
    # Tentar diferentes métodos de download
    if download_with_ytdlp(url, output_path):
        print("Download bem-sucedido com yt-dlp!")
        return output_path
    
    print("yt-dlp falhou, tentando método alternativo...")
    
    if download_with_requests(url, output_path):
        print("Download bem-sucedido com requests!")
        return output_path
    
    print("requests falhou, tentando gdown...")
    
    if download_with_gdown(url, output_path):
        print("Download bem-sucedido com gdown!")
        return output_path
    
    print("Todos os métodos de download falharam.")
    return None

def read_urls_from_file(file_path=URL_FILE):
    """Lê as URLs de um arquivo de texto."""
    if not os.path.exists(file_path):
        # Criar arquivo com exemplo se não existir
        with open(file_path, "w") as f:
            f.write("https://drive.google.com/file/d/1DTwXm5jdHZoI2V2E8zkKWb78IjAPEkaL/view?t=3\n")
            f.write("# Adicione mais URLs abaixo (uma por linha)\n")
        print(f"Arquivo {file_path} criado. Adicione as URLs dos vídeos (uma por linha) e execute novamente.")
        return []
    
    # Ler URLs do arquivo
    with open(file_path, "r") as f:
        urls = f.read().splitlines()
    
    # Filtrar comentários e linhas em branco
    valid_urls = [url.strip() for url in urls if url.strip() and not url.strip().startswith('#')]
    
    return valid_urls

def download_all_videos():
    """Baixa todos os vídeos listados no arquivo de URLs."""
    urls = read_urls_from_file()
    
    if not urls:
        print(f"Nenhuma URL encontrada em {URL_FILE}. Adicione URLs (uma por linha) e execute novamente.")
        return
    
    print(f"Iniciando download de {len(urls)} vídeo(s)...")
    
    successful_downloads = []
    
    for i, url in enumerate(urls):
        print(f"\n[{i+1}/{len(urls)}] Processando: {url}")
        result = download_meet_video(url, OUTPUT_DIR, i+1)
        
        if result:
            successful_downloads.append(result)
            print(f"Download concluído: {result}")
            
            # Aguardar entre downloads se houver mais vídeos e mais de um na lista
            if i < len(urls) - 1 and len(urls) > 1:
                wait_between_downloads()
        else:
            print(f"Falha ao baixar: {url}")
    
    total_success = len(successful_downloads)
    print(f"\nDownloads concluídos: {total_success}/{len(urls)}")
    
    if total_success > 0:
        print("\nArquivos baixados:")
        for file_path in successful_downloads:
            print(f"- {file_path}")

def main():
    """Função principal."""
    if len(sys.argv) > 1:
        # Se for fornecida uma URL como argumento
        url = sys.argv[1]
        result = download_meet_video(url)
        
        if result:
            print(f"Download concluído! Arquivo salvo em: {result}")
            return 0
        else:
            print("Falha no download.")
            return 1
    else:
        # Sem argumentos, baixar todos os vídeos do arquivo
        download_all_videos()
        return 0

if __name__ == "__main__":
    sys.exit(main())