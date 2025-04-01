# DownMeets

Ferramenta para download automático de vídeos de reuniões do Google Meet armazenados no Google Drive.

## Visão Geral

Este projeto permite baixar vídeos do Google Meet que foram compartilhados no Google Drive, mesmo quando configurados como "somente visualização" e sem opção de download direto.

## Técnica Utilizada

Este script é baseado na técnica descrita no artigo:
[How to download Google Meet meeting recordings set to "view only" mode](https://dev.to/gabrieldiem/how-to-download-google-meet-meeting-recordings-set-to-view-only-mode-4d2a) por Gabriel Diem.

A técnica consiste em:

1. **Contornar as restrições de visualização**: Quando o Google Drive limita o download de um vídeo, ele ainda precisa fornecer o streaming para visualização. Este script aproveita essa necessidade para extrair o conteúdo.

2. **Múltiplas abordagens de extração**:
   - **Método yt-dlp**: Utiliza o extrator especializado yt-dlp que pode extrair o stream de vídeo diretamente
   - **Método de URL direta**: Busca pela URL do stream de mídia no código HTML da página
   - **Método de API**: Usa pontos de acesso da API não documentada do Google Drive

3. **Simulação de navegador**: Usa headers HTTP específicos para simular um navegador real, contornando restrições de automação

4. **Tratamento de redirecionamentos**: Lida com páginas de confirmação e avisos que normalmente impedem o download automático

## Requisitos

- Python 3.8 ou superior
- Dependências (instaladas automaticamente):
  - requests
  - tqdm
  - gdown
  - yt-dlp

## Uso Simples

### Para baixar uma única URL:

```bash
python download_meet.py https://drive.google.com/file/d/SEU_ID_DO_ARQUIVO/view
```

### Para baixar múltiplas URLs:

1. Adicione as URLs ao arquivo `urls.txt` (uma por linha)
2. Execute:

```bash
python download_meet.py
```

## Configuração

As configurações principais estão definidas no início do arquivo `download_meet.py`:

```python
# Configurações
URL_FILE = "urls.txt"  # Arquivo com as URLs
OUTPUT_DIR = "meets"   # Diretório de saída
DELAY_MINUTES = 5      # Atraso entre downloads em minutos
```

## Funcionalidades

- **Múltiplos métodos de download**: Tenta diferentes técnicas para garantir o sucesso do download
- **Delay configurável**: Espera 5 minutos entre downloads quando há múltiplos arquivos
- **Barra de progresso**: Acompanhamento visual do progresso do download
- **Instalação automática de dependências**: Verifica e instala pacotes necessários
- **Tratamento de erros robusto**: Se um método falha, outros são tentados

## Como Funciona

O script utiliza três métodos diferentes para tentar baixar os vídeos:

1. **yt-dlp**: Biblioteca especializada em extrair vídeos de várias plataformas
2. **requests**: Download direto usando técnicas para contornar restrições
3. **gdown**: Biblioteca específica para downloads do Google Drive

Se um método falhar, o próximo é tentado automaticamente.

## Por que funciona?

A técnica funciona porque o Google Drive precisa entregar o conteúdo do vídeo ao navegador para reprodução, mesmo quando a opção de download está desativada. As bibliotecas especializadas como yt-dlp são capazes de:

1. Identificar os endpoints de streaming que o player do navegador usa
2. Extrair os cookies e tokens de autenticação necessários
3. Fazer requisições diretamente para esses endpoints
4. Salvar o stream de vídeo recebido localmente

Este método funciona mesmo quando o Google Drive mostra a mensagem "Opções de download desativadas" ou "Download indisponível", já que essas restrições são aplicadas na interface do usuário, não no nível da rede onde o script opera.

## Solução de Problemas

- **Arquivo vazio**: O script tentará automaticamente métodos alternativos
- **URLs incorretas**: Certifique-se de que a URL contém o ID do arquivo (`/d/ID_DO_ARQUIVO`)
- **Falha em todos os métodos**: Verifique se o arquivo existe e se você tem permissão para visualizá-lo