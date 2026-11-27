const fs = require('node:fs');
const path = require('node:path');
const {test, expect} = require('@playwright/test');

const VIDEO = path.join(__dirname, '..', '.fixtures', 'video.mp4');

const PNG_1PX = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==',
    'base64'
);

async function enviar(page, arquivo, conversao) {
    await page.goto('/');
    const [seletor] = await Promise.all([
        page.waitForEvent('filechooser'),
        page.getByRole('button', {name: /Arraste um arquivo aqui/}).click(),
    ]);
    await seletor.setFiles(arquivo);
    await page.getByRole('button', {name: new RegExp(conversao)}).click();
    await page.getByRole('button', {name: 'Converter', exact: true}).click();
}

async function baixar(page) {
    const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('link', {name: 'Baixar resultado'}).click(),
    ]);
    const conteudo = fs.readFileSync(await download.path());
    return {nome: download.suggestedFilename(), conteudo};
}

test('converte imagem PNG para WebP e baixa o resultado', async ({page}) => {
    await enviar(page, {name: 'pixel.png', mimeType: 'image/png', buffer: PNG_1PX}, 'Converter para WEBP');

    await expect(page.getByText(/^Pronto em/)).toBeVisible();
    const {nome, conteudo} = await baixar(page);

    expect(nome).toBe('pixel.webp');
    expect(conteudo.subarray(0, 4).toString()).toBe('RIFF');
    expect(conteudo.subarray(8, 12).toString()).toBe('WEBP');
});

test('vídeo mostra a barra de progresso até o WebM ficar pronto', async ({page}) => {
    await enviar(page, VIDEO, 'Converter para WebM');

    const barra = page.getByRole('progressbar', {name: 'Conversão do arquivo'});
    await expect(barra).toBeVisible({timeout: 60_000});
    await expect(barra).not.toHaveAttribute('aria-valuenow', '0');

    await expect(page.getByRole('link', {name: 'Baixar resultado'})).toBeVisible({timeout: 150_000});
    const {nome, conteudo} = await baixar(page);

    expect(nome).toBe('video.webm');
    expect(conteudo.subarray(0, 4).toString('hex')).toBe('1a45dfa3');
});

test('recarregar a página não perde o job em andamento', async ({page}) => {
    await enviar(page, VIDEO, 'Extrair áudio');
    await expect(page.getByText(/aguardando um worker livre|Convertendo…|^Pronto em/)).toBeVisible();

    await page.reload();

    await expect(page.getByRole('heading', {name: 'video.mp4'})).toBeVisible();
    await expect(page.getByRole('link', {name: 'Baixar resultado'})).toBeVisible({timeout: 60_000});
    const {nome} = await baixar(page);
    expect(nome).toBe('video.mp3');
});

test('arquivo corrompido termina com a mensagem de erro do worker', async ({page}) => {
    await enviar(
        page,
        {name: 'quebrado.mp4', mimeType: 'video/mp4', buffer: Buffer.from('isto nao e um video')},
        'Converter para WebM'
    );

    await expect(page.getByRole('alert')).toContainText('ffmpeg falhou', {timeout: 60_000});
    await expect(page.getByRole('button', {name: 'Ajustar e tentar de novo'})).toBeVisible();
});

test('o proxy do front não expõe a listagem de jobs', async ({request}) => {
    const resposta = await request.get('/api/jobs');
    expect(resposta.status()).toBe(403);
});