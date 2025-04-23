#!/usr/bin/env python3
"""
DownMeets - Ferramenta para download, transcrição e resumo de vídeos do Google Meet.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import dotenv
from dotenv import load_dotenv

from core import download, transcribe, summarize, utils


# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DownMeets")


def load_config() -> Dict:
    """Carrega as configurações do arquivo .env"""
    load_dotenv()
    
    # Configurações obrigatórias com valores padrão
    config = {
        "URL_FILE": os.getenv("URL_FILE", "urls.txt"),
        "DELAY_MINUTES": int(os.getenv("DELAY_MINUTES", "5")),
        "VIDEO_OUTPUT_DIR": os.getenv("VIDEO_OUTPUT_DIR", "output/videos"),
        "TRANSCRIPTION_OUTPUT_DIR": os.getenv("TRANSCRIPTION_OUTPUT_DIR", "output/transcriptions"),
        "SUMMARY_OUTPUT_DIR": os.getenv("SUMMARY_OUTPUT_DIR", "output/summaries"),
        "ENABLE_DOWNLOAD": os.getenv("ENABLE_DOWNLOAD", "true").lower() == "true",
        "ENABLE_TRANSCRIPTION": os.getenv("ENABLE_TRANSCRIPTION", "false").lower() == "true",
        "ENABLE_SUMMARY": os.getenv("ENABLE_SUMMARY", "false").lower() == "true",
        "TRANSCRIPTION_MODEL": os.getenv("TRANSCRIPTION_MODEL", "whisper-1"),
        "SUMMARY_MODEL": os.getenv("SUMMARY_MODEL", "gpt-4"),
        "SUMMARY_LANGUAGE": os.getenv("SUMMARY_LANGUAGE", "pt-br"),
    }
    
    # Sempre incluir a chave da API OpenAI, independentemente das configurações
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY não definida no .env, transcrição e resumo podem falhar.")
    config["OPENAI_API_KEY"] = api_key
    
    return config


def ensure_output_directories(config: Dict) -> None:
    """Garante que os diretórios de saída existam"""
    Path(config["VIDEO_OUTPUT_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(config["TRANSCRIPTION_OUTPUT_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(config["SUMMARY_OUTPUT_DIR"]).mkdir(parents=True, exist_ok=True)


def load_metadata() -> Dict:
    """Carrega os metadados existentes ou cria um novo arquivo"""
    metadata_path = Path("output/metadata.json")
    
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Arquivo de metadados corrompido. Criando novo.")
            return {}
    else:
        # Garantir que o diretório output exista
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        return {}


def save_metadata(metadata: Dict) -> None:
    """Salva os metadados no arquivo"""
    metadata_path = Path("output/metadata.json")
    
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def process_url(url: str, config: Dict, metadata: Dict, mode: str = "all") -> Optional[str]:
    """
    Processa uma URL: baixa, transcreve e resume conforme configuração e modo.
    
    Modos:
    - 'all': Executa todas as etapas habilitadas no config
    - 'download': Apenas faz o download
    - 'transcribe': Apenas faz a transcrição
    - 'summarize': Apenas faz o resumo
    """
    try:
        # Extrair ID da URL para identificação nos metadados
        file_id = download.extract_file_id(url)
        key = f"meet_{file_id}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Inicializar entrada nos metadados se não existir
        if key not in metadata:
            metadata[key] = {
                "url": url,
                "file_id": file_id,
                "created_at": datetime.now().isoformat()
            }
        
        # Etapa 1: Download do vídeo
        video_path = None
        if mode == "all" and config["ENABLE_DOWNLOAD"] or mode == "download":
            video_filename = f"video_{file_id}_{timestamp}.mp4"
            video_path = os.path.join(config["VIDEO_OUTPUT_DIR"], video_filename)
            
            logger.info(f"Baixando vídeo: {url}")
            success = download.download_meet_video(url, video_path)
            
            if success:
                metadata[key]["video_path"] = video_path
                metadata[key]["download_date"] = datetime.now().isoformat()
                save_metadata(metadata)
                logger.info(f"Vídeo baixado com sucesso: {video_path}")
            else:
                logger.error(f"Falha ao baixar vídeo: {url}")
                if mode == "download":
                    return None
        else:
            # Se não estamos fazendo download, usar o caminho do vídeo dos metadados
            if "video_path" in metadata[key]:
                video_path = metadata[key]["video_path"]
                if not os.path.exists(video_path):
                    logger.error(f"Vídeo não encontrado no caminho: {video_path}")
                    if mode in ["all", "transcribe"]:
                        return None
            elif mode in ["all", "transcribe"]:
                logger.error("Vídeo não encontrado nos metadados e download não está habilitado.")
                return None
        
        # Etapa 2: Transcrição do vídeo
        transcription_path = None
        if (mode == "all" and config["ENABLE_TRANSCRIPTION"] or mode == "transcribe") and video_path:
            # Verificar se já foi transcrito
            if "transcription_path" in metadata[key] and os.path.exists(metadata[key]["transcription_path"]):
                logger.info(f"Transcrição já existente: {metadata[key]['transcription_path']}")
                transcription_path = metadata[key]["transcription_path"]
            else:
                transcription_filename = f"transcription_{file_id}_{timestamp}.txt"
                transcription_path = os.path.join(config["TRANSCRIPTION_OUTPUT_DIR"], transcription_filename)
                
                # Obter a chave da API (garantir que exista)
                api_key = config.get("OPENAI_API_KEY")
                if not api_key:
                    logger.error("Chave da API OpenAI não encontrada. Utilize o argumento --api-key para fornecê-la.")
                    if mode == "transcribe":
                        return None
                
                logger.info(f"Transcrevendo vídeo: {video_path}")
                success = transcribe.transcribe_video(
                    video_path=video_path,
                    output_path=transcription_path,
                    model=config["TRANSCRIPTION_MODEL"],
                    api_key=api_key
                )
                
                if success:
                    metadata[key]["transcription_path"] = transcription_path
                    metadata[key]["transcription_date"] = datetime.now().isoformat()
                    save_metadata(metadata)
                    logger.info(f"Transcrição concluída: {transcription_path}")
                else:
                    logger.error(f"Falha ao transcrever vídeo: {video_path}")
                    if mode == "transcribe":
                        return None
        elif mode == "summarize" or (mode == "all" and config["ENABLE_SUMMARY"]):
            # Para resumo, precisamos apenas da transcrição
            if "transcription_path" in metadata[key] and os.path.exists(metadata[key]["transcription_path"]):
                transcription_path = metadata[key]["transcription_path"]
            else:
                logger.error("Nenhuma transcrição encontrada para este vídeo.")
                if mode == "summarize":
                    return None
        
        # Etapa 3: Resumo da transcrição
        if (mode == "all" and config["ENABLE_SUMMARY"] or mode == "summarize") and transcription_path:
            # Verificar se já foi resumido
            if "summary_path" in metadata[key] and os.path.exists(metadata[key]["summary_path"]):
                logger.info(f"Resumo já existente: {metadata[key]['summary_path']}")
            else:
                summary_filename = f"summary_{file_id}_{timestamp}.md"
                summary_path = os.path.join(config["SUMMARY_OUTPUT_DIR"], summary_filename)
                
                # Obter a chave da API (garantir que exista)
                api_key = config.get("OPENAI_API_KEY")
                if not api_key:
                    logger.error("Chave da API OpenAI não encontrada. Utilize o argumento --api-key para fornecê-la.")
                    if mode == "summarize":
                        return None
                
                logger.info(f"Gerando resumo da transcrição: {transcription_path}")
                success = summarize.generate_summary(
                    transcription_path=transcription_path,
                    output_path=summary_path,
                    model=config["SUMMARY_MODEL"],
                    language=config["SUMMARY_LANGUAGE"],
                    api_key=api_key
                )
                
                if success:
                    metadata[key]["summary_path"] = summary_path
                    metadata[key]["summary_date"] = datetime.now().isoformat()
                    save_metadata(metadata)
                    logger.info(f"Resumo concluído: {summary_path}")
                else:
                    logger.error(f"Falha ao gerar resumo da transcrição: {transcription_path}")
                    if mode == "summarize":
                        return None
        
        return key
    
    except Exception as e:
        logger.exception(f"Erro ao processar URL {url}: {str(e)}")
        return None


def read_urls(config: Dict) -> List[str]:
    """Lê as URLs do arquivo de entrada"""
    url_file = config["URL_FILE"]
    
    if not os.path.exists(url_file):
        logger.warning(f"Arquivo de URLs {url_file} não encontrado. Criando arquivo vazio.")
        with open(url_file, "w", encoding="utf-8") as f:
            f.write("# Adicione URLs de vídeos do Google Meet (uma por linha)\n")
        return []
    
    with open(url_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Filtrar comentários e linhas vazias
    urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return urls


def find_all_videos() -> List[str]:
    """Encontra todos os caminhos de vídeos nos metadados"""
    metadata = load_metadata()
    videos = []
    
    for key, data in metadata.items():
        if "video_path" in data and os.path.exists(data["video_path"]):
            videos.append(data["video_path"])
    
    return videos


def find_all_transcriptions() -> List[str]:
    """Encontra todos os caminhos de transcrições nos metadados"""
    metadata = load_metadata()
    transcriptions = []
    
    for key, data in metadata.items():
        if "transcription_path" in data and os.path.exists(data["transcription_path"]):
            transcriptions.append(data["transcription_path"])
    
    return transcriptions


def process_single_video(video_path: str, config: Dict, metadata: Dict, mode: str) -> Optional[str]:
    """Processa um único vídeo já baixado para transcrição ou resumo"""
    try:
        # Tentar encontrar o vídeo nos metadados
        found_key = None
        for key, data in metadata.items():
            if "video_path" in data and data["video_path"] == video_path:
                found_key = key
                break
        
        if not found_key:
            # Vídeo não está nos metadados, adicioná-lo
            file_name = os.path.basename(video_path)
            # Tentar extrair ID do nome do arquivo
            if file_name.startswith("video_"):
                parts = file_name.split("_")
                if len(parts) >= 2:
                    file_id = parts[1].split(".")[0]
                    key = f"meet_{file_id}"
                else:
                    # Gerar ID aleatório
                    import uuid
                    file_id = str(uuid.uuid4())[:8]
                    key = f"meet_{file_id}"
            else:
                # Gerar ID aleatório
                import uuid
                file_id = str(uuid.uuid4())[:8]
                key = f"meet_{file_id}"
            
            metadata[key] = {
                "file_id": file_id,
                "video_path": video_path,
                "created_at": datetime.now().isoformat(),
                "download_date": datetime.now().isoformat()
            }
            save_metadata(metadata)
        else:
            key = found_key
            file_id = metadata[key]["file_id"]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Transcricão
        if mode == "transcribe":
            transcription_filename = f"transcription_{file_id}_{timestamp}.txt"
            transcription_path = os.path.join(config["TRANSCRIPTION_OUTPUT_DIR"], transcription_filename)
            
            # Verificar se temos a chave da API
            api_key = config.get("OPENAI_API_KEY")
            if not api_key:
                logger.error("Chave da API OpenAI não encontrada. Utilize o argumento --api-key para fornecê-la.")
                return None
            
            logger.info(f"Transcrevendo vídeo: {video_path}")
            success = transcribe.transcribe_video(
                video_path=video_path,
                output_path=transcription_path,
                model=config.get("TRANSCRIPTION_MODEL", "whisper-1"),
                api_key=api_key
            )
            
            if success:
                metadata[key]["transcription_path"] = transcription_path
                metadata[key]["transcription_date"] = datetime.now().isoformat()
                save_metadata(metadata)
                logger.info(f"Transcrição concluída: {transcription_path}")
                return key
            else:
                logger.error(f"Falha ao transcrever vídeo: {video_path}")
                return None
                
        return key
    
    except Exception as e:
        logger.exception(f"Erro ao processar vídeo {video_path}: {str(e)}")
        return None


def process_single_transcription(transcription_path: str, config: Dict, metadata: Dict) -> Optional[str]:
    """Processa uma única transcrição para resumo"""
    try:
        # Tentar encontrar a transcrição nos metadados
        found_key = None
        for key, data in metadata.items():
            if "transcription_path" in data and data["transcription_path"] == transcription_path:
                found_key = key
                break
        
        if not found_key:
            # Transcrição não está nos metadados, adicioná-la
            file_name = os.path.basename(transcription_path)
            # Tentar extrair ID do nome do arquivo
            if file_name.startswith("transcription_"):
                parts = file_name.split("_")
                if len(parts) >= 2:
                    file_id = parts[1].split(".")[0]
                    key = f"meet_{file_id}"
                else:
                    # Gerar ID aleatório
                    import uuid
                    file_id = str(uuid.uuid4())[:8]
                    key = f"meet_{file_id}"
            else:
                # Gerar ID aleatório
                import uuid
                file_id = str(uuid.uuid4())[:8]
                key = f"meet_{file_id}"
            
            metadata[key] = {
                "file_id": file_id,
                "transcription_path": transcription_path,
                "created_at": datetime.now().isoformat(),
                "transcription_date": datetime.now().isoformat()
            }
            save_metadata(metadata)
        else:
            key = found_key
            file_id = metadata[key]["file_id"]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Resumo
        summary_filename = f"summary_{file_id}_{timestamp}.md"
        summary_path = os.path.join(config["SUMMARY_OUTPUT_DIR"], summary_filename)
        
        # Verificar se temos a chave da API
        api_key = config.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("Chave da API OpenAI não encontrada. Utilize o argumento --api-key para fornecê-la.")
            return None
        
        logger.info(f"Gerando resumo da transcrição: {transcription_path}")
        success = summarize.generate_summary(
            transcription_path=transcription_path,
            output_path=summary_path,
            model=config.get("SUMMARY_MODEL", "gpt-4"),
            language=config.get("SUMMARY_LANGUAGE", "pt-br"),
            api_key=api_key
        )
        
        if success:
            metadata[key]["summary_path"] = summary_path
            metadata[key]["summary_date"] = datetime.now().isoformat()
            save_metadata(metadata)
            logger.info(f"Resumo concluído: {summary_path}")
            return key
        else:
            logger.error(f"Falha ao gerar resumo da transcrição: {transcription_path}")
            return None
    
    except Exception as e:
        logger.exception(f"Erro ao processar transcrição {transcription_path}: {str(e)}")
        return None


def setup_argparse() -> argparse.ArgumentParser:
    """Configura os argumentos de linha de comando"""
    parser = argparse.ArgumentParser(
        description="DownMeets - Ferramenta para download, transcrição e resumo de vídeos do Google Meet"
    )
    
    # Modos de operação
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--download", "-d", 
        action="store_true", 
        help="Apenas realizar o download dos vídeos"
    )
    mode_group.add_argument(
        "--transcribe", "-t", 
        action="store_true", 
        help="Apenas transcrever vídeos"
    )
    mode_group.add_argument(
        "--summarize", "-s", 
        action="store_true", 
        help="Apenas gerar resumos de transcrições"
    )
    
    # Parâmetros adicionais
    parser.add_argument(
        "--input", "-i",
        help="Caminho específico para um vídeo ou transcrição como entrada"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Processar todos os vídeos ou transcrições disponíveis"
    )
    parser.add_argument(
        "--url", "-u",
        help="URL específica para download, transcrição e/ou resumo"
    )
    
    # Adicionar argumento para a chave da API OpenAI
    parser.add_argument(
        "--api-key", "-k",
        help="Chave da API OpenAI para transcrição e resumo"
    )
    
    return parser


def main():
    """Função principal do programa"""
    # Verificar se existe um arquivo .env, caso contrário criar um modelo
    if not os.path.exists(".env"):
        logger.info("Arquivo .env não encontrado. Criando modelo...")
        with open(".env", "w", encoding="utf-8") as f:
            f.write("""# Configurações do DownMeets
URL_FILE=urls.txt
DELAY_MINUTES=5

# Diretórios
VIDEO_OUTPUT_DIR=output/videos
TRANSCRIPTION_OUTPUT_DIR=output/transcriptions
SUMMARY_OUTPUT_DIR=output/summaries

# Controle de funcionalidades
ENABLE_DOWNLOAD=true
ENABLE_TRANSCRIPTION=false
ENABLE_SUMMARY=false

# Configurações de transcrição e resumo
OPENAI_API_KEY=
TRANSCRIPTION_MODEL=whisper-1
SUMMARY_MODEL=gpt-4
SUMMARY_LANGUAGE=pt-br
""")
        logger.info("Arquivo .env criado. Por favor, configure-o e execute novamente.")
        return 1
    
    # Analisar argumentos de linha de comando
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Carregar configurações
    config = load_config()
    
    # Adicionar a chave da API fornecida via linha de comando (prioridade sobre .env)
    if args.api_key:
        config["OPENAI_API_KEY"] = args.api_key
        logger.info("Usando chave da API fornecida via linha de comando")
    
    # Determinar o modo de operação
    mode = "all"
    if args.download:
        mode = "download"
    elif args.transcribe:
        mode = "transcribe"
    elif args.summarize:
        mode = "summarize"
    
    # Garantir que os diretórios de saída existam
    ensure_output_directories(config)
    
    # Carregar metadados
    metadata = load_metadata()
    
    # Verificar dependências específicas para o modo
    need_openai = mode in ["transcribe", "summarize", "all"] and (
        config["ENABLE_TRANSCRIPTION"] or config["ENABLE_SUMMARY"]
    )
    need_ffmpeg = mode in ["transcribe", "all"] and config["ENABLE_TRANSCRIPTION"]
    
    missing_deps = utils.check_dependencies(
        need_openai=need_openai,
        need_ffmpeg=need_ffmpeg
    )
    
    if missing_deps:
        logger.error(f"Dependências ausentes: {', '.join(missing_deps)}")
        return 1
    
    # Processar conforme o modo e os parâmetros
    if args.url:
        # Processar uma URL específica
        logger.info(f"Processando URL específica: {args.url}")
        process_url(args.url, config, metadata, mode)
    elif args.input:
        # Processar um arquivo específico (vídeo ou transcrição)
        input_path = args.input
        if not os.path.exists(input_path):
            logger.error(f"Arquivo não encontrado: {input_path}")
            return 1
        
        if mode == "transcribe":
            # Transcrever um vídeo específico
            logger.info(f"Transcrevendo vídeo específico: {input_path}")
            process_single_video(input_path, config, metadata, mode)
        elif mode == "summarize":
            # Resumir uma transcrição específica
            logger.info(f"Gerando resumo para transcrição específica: {input_path}")
            process_single_transcription(input_path, config, metadata)
        else:
            logger.error(f"Modo '{mode}' não suportado com parâmetro --input")
            return 1
    elif args.all:
        # Processar todos os arquivos disponíveis
        if mode == "download":
            # Baixar todas as URLs do arquivo
            urls = read_urls(config)
            if not urls:
                logger.warning(f"Nenhuma URL encontrada em {config['URL_FILE']}.")
                return 0
            
            logger.info(f"Baixando {len(urls)} vídeo(s)...")
            for i, url in enumerate(urls):
                logger.info(f"[{i+1}/{len(urls)}] Baixando: {url}")
                process_url(url, config, metadata, mode)
                
                # Aguardar entre downloads se houver mais URLs
                if i < len(urls) - 1:
                    utils.wait_between_items(config["DELAY_MINUTES"])
        
        elif mode == "transcribe":
            # Transcrever todos os vídeos disponíveis
            videos = find_all_videos()
            if not videos:
                logger.warning("Nenhum vídeo encontrado para transcrição.")
                return 0
            
            logger.info(f"Transcrevendo {len(videos)} vídeo(s)...")
            for i, video_path in enumerate(videos):
                logger.info(f"[{i+1}/{len(videos)}] Transcrevendo: {video_path}")
                process_single_video(video_path, config, metadata, mode)
                
                # Aguardar entre transcrições se houver mais vídeos
                if i < len(videos) - 1:
                    utils.wait_between_items(config["DELAY_MINUTES"])
        
        elif mode == "summarize":
            # Resumir todas as transcrições disponíveis
            transcriptions = find_all_transcriptions()
            if not transcriptions:
                logger.warning("Nenhuma transcrição encontrada para resumo.")
                return 0
            
            logger.info(f"Gerando resumos para {len(transcriptions)} transcrição(ões)...")
            for i, transcription_path in enumerate(transcriptions):
                logger.info(f"[{i+1}/{len(transcriptions)}] Resumindo: {transcription_path}")
                process_single_transcription(transcription_path, config, metadata)
                
                # Aguardar entre resumos se houver mais transcrições
                if i < len(transcriptions) - 1:
                    utils.wait_between_items(config["DELAY_MINUTES"])
        
        else:  # mode == "all"
            # Processar todas as URLs com todas as etapas habilitadas
            urls = read_urls(config)
            if not urls:
                logger.warning(f"Nenhuma URL encontrada em {config['URL_FILE']}.")
                return 0
            
            logger.info(f"Processando {len(urls)} URL(s)...")
            for i, url in enumerate(urls):
                logger.info(f"[{i+1}/{len(urls)}] Processando: {url}")
                process_url(url, config, metadata, mode)
                
                # Aguardar entre processamentos se houver mais URLs
                if i < len(urls) - 1:
                    utils.wait_between_items(config["DELAY_MINUTES"])
    else:
        # Comportamento padrão: processar URLs do arquivo conforme configuração
        urls = read_urls(config)
        if not urls:
            logger.warning(f"Nenhuma URL encontrada em {config['URL_FILE']}.")
            return 0
        
        logger.info(f"Processando {len(urls)} URL(s)...")
        for i, url in enumerate(urls):
            logger.info(f"[{i+1}/{len(urls)}] Processando: {url}")
            process_url(url, config, metadata, mode)
            
            # Aguardar entre processamentos se houver mais URLs
            if i < len(urls) - 1:
                utils.wait_between_items(config["DELAY_MINUTES"])
    
    logger.info("Processamento concluído!")
    return 0


if __name__ == "__main__":
    sys.exit(main())