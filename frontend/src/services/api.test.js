import { mensagemDeErro } from './api';

  function erroHttp(status, detail) {
    return { response: { status, data: detail === undefined ? '' : { detail } } };
  }

  test('sem resposta fala da conexão', () => {
    expect(mensagemDeErro(new Error('Network Error'))).toMatch(/Sem resposta do servidor/);
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