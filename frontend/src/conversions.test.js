import { EXTENSOES_SUPORTADAS, camposValidos, extensaoDe, opcoesPara } from './conversions';

const OPERATIONS_DA_API = [
  'image.thumbnail',
  'csv.validate',
  'excel.to-csv',
  'pdf.extract-text',
  'pdf.merge',
  'pdf.watermark',
  'video.transcode',
  'audio.extract',
  'ocr.extract',
  'document.convert',
];

const ids = (nome) => opcoesPara(nome).map((opcao) => opcao.id);
const opcao = (nome, id) => opcoesPara(nome).find((item) => item.id === id);

describe('extensaoDe', () => {
  test.each([
    ['foto.JPG', 'jpg'],
    ['relatorio.final.pdf', 'pdf'],
    ['sem-extensao', ''],
    ['.gitignore', ''],
    ['termina-com-ponto.', ''],
  ])('%s -> "%s"', (nome, esperado) => {
    expect(extensaoDe(nome)).toBe(esperado);
  });
});

describe('opcoesPara', () => {
  test('imagem nao oferece conversao para o proprio formato', () => {
    expect(ids('foto.png')).not.toContain('imagem-png');
    expect(ids('foto.png')).toEqual(
      expect.arrayContaining(['imagem-webp', 'imagem-jpeg', 'imagem-miniatura', 'ocr'])
    );
  });

  test('jpg e jpeg contam como o mesmo formato', () => {
    expect(ids('a.jpg')).not.toContain('imagem-jpeg');
    expect(ids('a.jpeg')).not.toContain('imagem-jpeg');
  });

  test('troca para JPG envia "jpeg", que e o nome que o Pillow aceita', () => {
    expect(opcao('a.png', 'imagem-jpeg').parametros({})).toEqual({
      width: 4096,
      height: 4096,
      format: 'jpeg',
    });
  });

  test('xlsx oferece CSV e PDF; xls so PDF', () => {
    expect(ids('vendas.xlsx')).toEqual(['planilha-csv', 'documento-pdf']);
    expect(ids('vendas.xls')).toEqual(['documento-pdf']);
  });

  test('video oferece o outro container e extracao de audio', () => {
    expect(ids('clipe.mp4')).toEqual(['video-webm', 'video-audio-mp3']);
    expect(ids('clipe.mov')).toEqual(['video-mp4', 'video-webm', 'video-audio-mp3']);
  });

  test('wav nao envia bitrate', () => {
    expect(opcao('musica.mp3', 'audio-wav').parametros({})).toEqual({ format: 'wav' });
  });

  test('csv e extensoes desconhecidas nao tem opcoes', () => {
    expect(opcoesPara('dados.csv')).toEqual([]);
    expect(opcoesPara('programa.exe')).toEqual([]);
    expect(opcoesPara('arquivo.constructor')).toEqual([]);
  });

  test('toda opcao aponta para uma operation que existe na API', () => {
    EXTENSOES_SUPORTADAS.forEach((ext) => {
      opcoesPara(`arquivo.${ext}`).forEach((item) => {
        expect(OPERATIONS_DA_API).toContain(item.operation);
      });
    });
  });
});

describe("marca d'agua", () => {
  const marca = opcao('contrato.pdf', 'pdf-marca-dagua');

  test('exige texto preenchido', () => {
    expect(camposValidos(marca, {})).toBe(false);
    expect(camposValidos(marca, { text: '   ' })).toBe(false);
    expect(camposValidos(marca, { text: 'RASCUNHO' })).toBe(true);
  });

  test('envia o texto sem espacos nas pontas', () => {
    expect(marca.parametros({ text: '  RASCUNHO ' }).text).toBe('RASCUNHO');
  });
});
