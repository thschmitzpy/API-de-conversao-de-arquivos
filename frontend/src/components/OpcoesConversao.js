import { EXTENSOES_SUPORTADAS, camposValidos } from '../conversions';

export default function OpcoesConversao({
  extensao,
  opcoes,
  selecionada,
  valores,
  onSelecionar,
  onAlterarValor,
  onConverter,
}) {
  if (opcoes.length === 0) {
    return (
      <section className="painel painel--aviso">
        <strong>Ainda não convertemos arquivos .{extensao || '?'} por aqui.</strong>
        <p>Formatos aceitos: {EXTENSOES_SUPORTADAS.join(', ')}.</p>
      </section>
    );
  }

  const pronta = Boolean(selecionada) && camposValidos(selecionada, valores);

  function aoEnviar(evento) {
    evento.preventDefault();
    if (pronta) {
      onConverter();
    }
  }

  return (
    <form className="painel" onSubmit={aoEnviar}>
      <h2>O que fazer com o arquivo?</h2>

      <div className="opcoes" role="radiogroup" aria-label="Conversões disponíveis">
        {opcoes.map((opcao) => {
          const ativa = selecionada?.id === opcao.id;
          return (
            <button
              key={opcao.id}
              type="button"
              role="radio"
              aria-checked={ativa}
              className={ativa ? 'opcao opcao--ativa' : 'opcao'}
              onClick={() => onSelecionar(opcao)}
            >
              <span className="opcao__saida">.{opcao.saida}</span>
              <strong>{opcao.titulo}</strong>
              <span className="opcao__descricao">{opcao.descricao}</span>
            </button>
          );
        })}
      </div>

      {selecionada?.campos?.map((campo) => (
        <label key={campo.nome} className="campo">
          <span>{campo.rotulo}</span>
          <input
            type="text"
            value={valores[campo.nome] ?? ''}
            placeholder={campo.placeholder}
            maxLength={campo.maxLength}
            onChange={(evento) => onAlterarValor(campo.nome, evento.target.value)}
          />
        </label>
      ))}

      <button type="submit" className="botao botao--primario" disabled={!pronta}>
        Converter
      </button>
    </form>
  );
}
