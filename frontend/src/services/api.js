import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export function criarJob(arquivo, operation, parameters, onProgresso) {
  const form = new FormData();
  form.append('file', arquivo);
  form.append('operation', operation);
  form.append('parameters', JSON.stringify(parameters));

  return api
    .post('/jobs', form, {
      onUploadProgress: (evento) => {
        if (evento.total) {
          onProgresso(Math.round((evento.loaded / evento.total) * 100));
        }
      },
    })
    .then((resposta) => resposta.data);
}

export function consultarJob(jobId, signal) {
  return api.get(`/jobs/${jobId}`, { signal }).then((resposta) => resposta.data);
}

export function urlDownload(jobId) {
  return `/api/jobs/${jobId}/download`;
}

export function mensagemDeErro(erro) {
  const status = erro.response?.status;
  const detail = erro.response?.data?.detail;

  if (!erro.response) {
    return 'Não foi possível falar com a API. Ela está de pé?';
  }
  if (status === 429) {
    return 'Muitas requisições em pouco tempo. Aguarde um minuto e tente de novo.';
  }
  if (status === 401 || status === 403) {
    return 'O front não está autorizado na API (confira a CONVERSOR_API_KEY).';
  }
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join('; ');
  }
  return `Erro inesperado (HTTP ${status}).`;
}
