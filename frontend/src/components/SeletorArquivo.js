import { useRef, useState } from 'react';
import { EXTENSOES_SUPORTADAS, extensaoDe } from '../conversions';
import { formatarBytes } from '../formatar';

const ACCEPT = EXTENSOES_SUPORTADAS.map((ext) => `.${ext}`).join(',');

export default function SeletorArquivo({ arquivo, onSelecionar }) {
  const inputRef = useRef(null);
  const [arrastando, setArrastando] = useState(false);

  function escolher(lista) {
    const primeiro = lista?.[0];
    if (primeiro) {
      onSelecionar(primeiro);
    }
  }

  function abrirExplorador() {
    inputRef.current.click();
  }

  function aoArrastarPorCima(evento) {
    evento.preventDefault();
    setArrastando(true);
  }

  function aoSairDaArea(evento) {
    if (!evento.currentTarget.contains(evento.relatedTarget)) {
      setArrastando(false);
    }
  }

  function aoSoltar(evento) {
    evento.preventDefault();
    setArrastando(false);
    escolher(evento.dataTransfer.files);
  }

  const classes = [
    'seletor',
    arrastando && 'seletor--arrastando',
    arquivo && 'seletor--com-arquivo',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <section
      className={classes}
      onDragOver={aoArrastarPorCima}
      onDragLeave={aoSairDaArea}
      onDrop={aoSoltar}
    >
      <input
        ref={inputRef}
        type="file"
        hidden
        accept={ACCEPT}
        onChange={(evento) => {
          escolher(evento.target.files);
          evento.target.value = '';
        }}
      />

      {arquivo ? (
        <div className="seletor__arquivo">
          <span className="seletor__extensao">{extensaoDe(arquivo.name) || '?'}</span>
          <div>
            <strong title={arquivo.name}>{arquivo.name}</strong>
            <small>{formatarBytes(arquivo.size)}</small>
          </div>
          <button type="button" className="botao botao--secundario" onClick={abrirExplorador}>
            Trocar arquivo
          </button>
        </div>
      ) : (
        <button type="button" className="seletor__vazio" onClick={abrirExplorador}>
          <span className="seletor__icone" aria-hidden="true">⇪</span>
          <strong>Arraste um arquivo aqui</strong>
          <span>ou clique para escolher no computador</span>
          <small>Até 100 MB · imagens, PDF, Office, vídeo, áudio e ZIP de PDFs</small>
        </button>
      )}
    </section>
  );
}
