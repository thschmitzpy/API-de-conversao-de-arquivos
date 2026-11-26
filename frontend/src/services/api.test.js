import axios from 'axios';
  import { consultarJob, criarJob, mensagemDeErro, urlDownload } from './api';

  // O api.js cria a instância no import: o mock devolve sempre o mesmo objeto.
  jest.mock('axios', () => {
    const instancia = { post: jest.fn(), get: jest.fn() };
    return { __esModule: true, default: { create: () => instancia } };
  });

  const http = axios.create();

  function erroHttp(status, detail) {
    return { response: { status, data: detail === undefined ? '' : { detail } } };
  }

  test('criarJob envia o arquivo em multipart e reporta o progresso', async () => {
    http.post.mockImplementation((url, form, config) => {
      config.onUploadProgress({ loaded: 50, total: 200 });
      return Promise.resolve({ data: { id: 'abc' } });
    });
    const onProgresso = jest.fn();
    const arquivo = new File(['conteudo'], 'foto.png');

    const criado = await criarJob(arquivo, 'image.thumbnail', { width: 256 }, onProgresso);

    const [url, form] = http.post.mock.calls[0];
    expect(url).toBe('/jobs');
    expect(form.get('file')).toBe(arquivo);
    expect(form.get('operation')).toBe('image.thumbnail');
    expect(JSON.parse(form.get('parameters'))).toEqual({ width: 256 });
    expect(onProgresso).toHaveBeenCalledWith(25);
    expect(criado).toEqual({ id: 'abc' });
  });

  test('consultarJob repassa o signal para poder cancelar', async () => {
    http.get.mockResolvedValue({ data: { status: 'DONE' } });
    const { signal } = new AbortController();

    expect(await consultarJob('abc', signal)).toEqual({ status: 'DONE' });
    expect(http.get).toHaveBeenCalledWith('/jobs/abc', { signal });
  });

  test('urlDownload passa pelo proxy do front', () => {
    expect(urlDownload('abc')).toBe('/api/jobs/abc/download');
  });

  test('sem resposta fala da conexão', () => {
    expect(mensagemDeErro(new Error('Network Error'))).toMatch(/Sem resposta do servidor/);
  });

  test('429 pede para aguardar', () => {
    expect(mensagemDeErro(erroHttp(429))).toMatch(/Aguarde um minuto/);
  });

  test('401 e 403 apontam a chave do front', () => {
    expect(mensagemDeErro(erroHttp(401))).toMatch(/CONVERSOR_API_KEY/);
    expect(mensagemDeErro(erroHttp(403))).toMatch(/CONVERSOR_API_KEY/);
  });

  test('5xx não expõe o detail interno', () => {
    expect(mensagemDeErro(erroHttp(502, 'Falha ao salvar arquivo no storage'))).toMatch(
      /servidor está com problemas/
    );
    expect(mensagemDeErro(erroHttp(504))).toMatch(/servidor está com problemas/);
  });

  test('413 do nginx, sem JSON, vira mensagem de limite', () => {
    expect(mensagemDeErro(erroHttp(413))).toMatch(/limite de envio/);
  });

  test('404 explica que a conversão sumiu', () => {
    expect(mensagemDeErro(erroHttp(404, 'Job nao encontrado'))).toMatch(/não foi encontrada/);
  });

  test('400 repassa o detail da API', () => {
    expect(mensagemDeErro(erroHttp(400, 'Arquivo vazio'))).toBe('Arquivo vazio');
  });

  test('422 com lista de erros do pydantic não mostra o texto em inglês', () => {
    const detail = [{ msg: 'Input should be a valid string' }];
    expect(mensagemDeErro(erroHttp(422, detail))).toBe('A requisição foi recusada (HTTP 422).');
  });