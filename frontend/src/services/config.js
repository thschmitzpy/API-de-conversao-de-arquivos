// Limites publicados pelo nginx em /config.json. No `npm start` o arquivo não
// existe (o dev server devolve o index.html) e o front fica com o padrão.
export async function carregarLimiteUpload() {
  try {
    const resposta = await fetch('/config.json', { cache: 'no-store' });
    if (!resposta.ok) {
      return null;
    }
    const { maxUploadMb } = await resposta.json();
    return Number.isInteger(maxUploadMb) && maxUploadMb > 0 ? maxUploadMb * 1024 * 1024 : null;
  } catch {
    return null;
  }
}
