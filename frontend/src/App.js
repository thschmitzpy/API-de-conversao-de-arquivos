import { useEffect, useState } from 'react';
import './App.css';
import Andamento from './components/Andamento';
import OpcoesConversao from './components/OpcoesConversao';
import SeletorArquivo from './components/SeletorArquivo';
import { LIMITE_UPLOAD_BYTES, extensaoDe, opcoesPara } from './conversions';
import { formatarBytes } from './formatar';
import useBloquearDrop from './hooks/useBloquearDrop';
import { criarJob, mensagemDeErro } from './services/api';
import { carregarLimiteUpload } from './services/config';
import { carregarJob, esquecerJob, salvarJob } from './services/jobSalvo';

function envioRestaurado() {
  const salvo = carregarJob();
  return salvo ? { ...salvo, progresso: 100, erro: null } : null;
}

export default function App() {
  const [arquivo, setArquivo] = useState(null);
  const [opcao, setOpcao] = useState(null);
  const [valores, setValores] = useState({});
  const [envio, setEnvio] = useState(envioRestaurado);
  const [limiteBytes, setLimiteBytes] = useState(LIMITE_UPLOAD_BYTES);

  useBloquearDrop();

  useEffect(() => {
    carregarLimiteUpload().then((bytes) => {
      if (bytes) {
        setLimiteBytes(bytes);
      }
    });
  }, []);

  const opcoes = arquivo ? opcoesPara(arquivo.name) : [];
  const muitoGrande = Boolean(arquivo) && arquivo.size > limiteBytes;

  function selecionarArquivo(novo) {
    const disponiveis = opcoesPara(novo.name);
    setArquivo(novo);
    setOpcao(disponiveis.length === 1 ? disponiveis[0] : null);
    setValores({});
  }

  async function converter() {
    const descricao = { nomeArquivo: arquivo.name, titulo: opcao.titulo };
    setEnvio({ ...descricao, progresso: 0, jobId: null, erro: null });
    try {
      const criado = await criarJob(arquivo, opcao.operation, opcao.parametros(valores), (progresso) =>
        setEnvio((atual) => ({ ...atual, progresso }))
      );
      salvarJob({ ...descricao, jobId: criado.id });
      setEnvio((atual) => ({ ...atual, progresso: 100, jobId: criado.id }));
    } catch (erro) {
      setEnvio((atual) => ({ ...atual, erro: mensagemDeErro(erro) }));
    }
  }

  function voltarAoArquivo() {
    esquecerJob();
    setEnvio(null);
  }

  function recomecar() {
    esquecerJob();
    setArquivo(null);
    setOpcao(null);
    setValores({});
    setEnvio(null);
  }

  return (
    <div className="app">
      <header className="topo">
        <h1>Conversor de Arquivos</h1>
        <p>
          Imagens, PDFs, documentos Office, vídeo e áudio. O processamento roda em segundo plano e o
          resultado fica pronto para baixar.
        </p>
      </header>

      <main className="conteudo">
        {envio ? (
          <Andamento
            nomeArquivo={envio.nomeArquivo}
            titulo={envio.titulo}
            progresso={envio.progresso}
            jobId={envio.jobId}
            erroEnvio={envio.erro}
            onVoltarAoArquivo={arquivo ? voltarAoArquivo : null}
            onRecomecar={recomecar}
          />
        ) : (
          <>
            <SeletorArquivo arquivo={arquivo} limiteBytes={limiteBytes} onSelecionar={selecionarArquivo} />

            {muitoGrande && (
              <p className="alerta alerta--erro" role="alert">
                O arquivo tem {formatarBytes(arquivo.size)}; o limite é{' '}
                {formatarBytes(limiteBytes)}.
              </p>
            )}

            {arquivo && !muitoGrande && (
              <OpcoesConversao
                extensao={extensaoDe(arquivo.name)}
                opcoes={opcoes}
                selecionada={opcao}
                valores={valores}
                onSelecionar={setOpcao}
                onAlterarValor={(nome, valor) => setValores((atuais) => ({ ...atuais, [nome]: valor }))}
                onConverter={converter}
              />
            )}
          </>
        )}
      </main>

      <footer className="rodape">FastAPI · Celery · MinIO · React (projeto de portfólio)</footer>
    </div>
  );
}
