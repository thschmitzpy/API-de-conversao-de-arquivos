// Mapa extensão -> conversões oferecidas na interface. Cada opção monta os
// `parameters` aceitos pelo processor correspondente no worker.

export const LIMITE_UPLOAD_BYTES = 100 * 1024 * 1024;

// O thumbnail do Pillow nunca amplia a imagem: com um teto alto, a operação
// vira só troca de formato (imagens maiores que isso são reduzidas).
const TETO_IMAGEM = 4096;

const FORMATOS_IMAGEM = [
  {
    format: 'webp',
    rotulo: 'WEBP',
    extensoes: ['webp'],
    descricao: 'Formato moderno e leve, ideal para sites.',
  },
  {
    format: 'png',
    rotulo: 'PNG',
    extensoes: ['png'],
    descricao: 'Sem perda de qualidade e com transparência.',
  },
  {
    format: 'jpeg',
    rotulo: 'JPG',
    extensoes: ['jpg', 'jpeg'],
    descricao: 'Compatível com tudo, mas sem transparência.',
  },
];

const FORMATOS_AUDIO = [
  { format: 'mp3', descricao: 'Compatível com qualquer player.' },
  { format: 'wav', descricao: 'Sem compressão: qualidade máxima, arquivo grande.' },
  { format: 'ogg', descricao: 'Formato aberto (Vorbis) e leve.' },
  { format: 'aac', descricao: 'Boa qualidade em arquivos pequenos.' },
];

const PARA_PDF = {
  id: 'documento-pdf',
  titulo: 'Converter para PDF',
  descricao: 'Gera um PDF com o mesmo layout do documento.',
  operation: 'document.convert',
  saida: 'pdf',
  parametros: () => ({}),
};

function ocr(descricao) {
  return {
    id: 'ocr',
    titulo: 'Extrair texto (OCR)',
    descricao,
    operation: 'ocr.extract',
    saida: 'txt',
    parametros: () => ({ lang: 'por+eng', output_format: 'text' }),
  };
}

function opcoesImagem(ext) {
  const trocas = FORMATOS_IMAGEM.filter((formato) => !formato.extensoes.includes(ext)).map(
    (formato) => ({
      id: `imagem-${formato.format}`,
      titulo: `Converter para ${formato.rotulo}`,
      descricao: formato.descricao,
      operation: 'image.thumbnail',
      saida: formato.extensoes[0],
      parametros: () => ({ width: TETO_IMAGEM, height: TETO_IMAGEM, format: formato.format }),
    })
  );

  return [
    ...trocas,
    {
      id: 'imagem-miniatura',
      titulo: 'Gerar miniatura',
      descricao: 'Reduz para caber em 256×256 px, mantendo a proporção.',
      operation: 'image.thumbnail',
      saida: ext,
      parametros: () => ({ width: 256, height: 256 }),
    },
    ocr('Lê o texto da imagem em português e inglês.'),
  ];
}

function opcoesPdf() {
  return [
    {
      id: 'pdf-texto',
      titulo: 'Extrair texto',
      descricao: 'Copia o texto do PDF para um arquivo .txt.',
      operation: 'pdf.extract-text',
      saida: 'txt',
      parametros: () => ({ output_format: 'text' }),
    },
    ocr('Para PDFs escaneados: lê as páginas como imagem.'),
    {
      id: 'pdf-marca-dagua',
      titulo: "Adicionar marca d'água",
      descricao: 'Escreve um texto na diagonal de todas as páginas.',
      operation: 'pdf.watermark',
      saida: 'pdf',
      campos: [
        {
          nome: 'text',
          rotulo: "Texto da marca d'água",
          placeholder: 'CONFIDENCIAL',
          obrigatorio: true,
          maxLength: 60,
        },
      ],
      parametros: (valores) => ({
        text: valores.text.trim(),
        position: 'diagonal',
        opacity: 0.3,
        color: 'gray',
      }),
    },
  ];
}

function opcoesZip() {
  return [
    {
      id: 'zip-juntar-pdfs',
      titulo: 'Juntar PDFs do ZIP',
      descricao: 'Une os PDFs do ZIP (mínimo 2) em ordem alfabética.',
      operation: 'pdf.merge',
      saida: 'pdf',
      parametros: () => ({}),
    },
  ];
}

function opcoesXlsx() {
  return [
    {
      id: 'planilha-csv',
      titulo: 'Converter para CSV',
      descricao: 'Separado por ponto e vírgula, abre direto no Excel em português.',
      operation: 'excel.to-csv',
      saida: 'csv',
      parametros: () => ({ delimiter: ';', include_header: true }),
    },
    PARA_PDF,
  ];
}

function opcoesDocumento() {
  return [PARA_PDF];
}

function opcoesVideo(ext) {
  const containers = [
    {
      format: 'mp4',
      titulo: 'Converter para MP4',
      descricao: 'O formato mais compatível (H.264 + AAC).',
    },
    {
      format: 'webm',
      titulo: 'Converter para WebM',
      descricao: 'Formato aberto para web (VP9 + Opus).',
    },
  ];

  return [
    ...containers
      .filter((container) => container.format !== ext)
      .map((container) => ({
        id: `video-${container.format}`,
        titulo: container.titulo,
        descricao: container.descricao,
        operation: 'video.transcode',
        saida: container.format,
        parametros: () => ({ format: container.format }),
      })),
    {
      id: 'video-audio-mp3',
      titulo: 'Extrair áudio (MP3)',
      descricao: 'Separa só a trilha de áudio do vídeo.',
      operation: 'audio.extract',
      saida: 'mp3',
      parametros: () => ({ format: 'mp3' }),
    },
  ];
}

function opcoesAudio(ext) {
  return FORMATOS_AUDIO.filter((formato) => formato.format !== ext).map((formato) => ({
    id: `audio-${formato.format}`,
    titulo: `Converter para ${formato.format.toUpperCase()}`,
    descricao: formato.descricao,
    operation: 'audio.extract',
    saida: formato.format,
    parametros: () => ({ format: formato.format }),
  }));
}

// Map em vez de objeto literal: "arquivo.constructor" não pode achar nada.
const GERADORES = new Map();

function registrar(extensoes, gerar) {
  extensoes.forEach((ext) => GERADORES.set(ext, gerar));
}

registrar(['jpg', 'jpeg', 'png', 'webp', 'gif'], opcoesImagem);
registrar(['pdf'], opcoesPdf);
registrar(['zip'], opcoesZip);
// openpyxl só lê xlsx; xls e ods vão apenas para PDF via LibreOffice.
registrar(['xlsx'], opcoesXlsx);
registrar(['docx', 'doc', 'odt', 'rtf', 'xls', 'ods', 'pptx', 'ppt', 'odp'], opcoesDocumento);
registrar(['mp4', 'mov', 'mkv', 'avi', 'webm'], opcoesVideo);
registrar(['mp3', 'wav', 'ogg', 'aac', 'm4a', 'flac'], opcoesAudio);

export const EXTENSOES_SUPORTADAS = [...GERADORES.keys()].sort();

export function extensaoDe(nomeArquivo) {
  const ponto = nomeArquivo.lastIndexOf('.');
  if (ponto <= 0 || ponto === nomeArquivo.length - 1) {
    return '';
  }
  return nomeArquivo.slice(ponto + 1).toLowerCase();
}

export function opcoesPara(nomeArquivo) {
  const ext = extensaoDe(nomeArquivo);
  const gerar = GERADORES.get(ext);
  return gerar ? gerar(ext) : [];
}

export function camposValidos(opcao, valores) {
  return (opcao.campos ?? []).every(
    (campo) => !campo.obrigatorio || (valores[campo.nome] ?? '').trim() !== ''
  );
}
