import {useRef, useState} from 'react';
import {consultarJob, mensagemDeErro, urlDownload} from '../services/api';


export default function BotaoDownload({jobId, onExpirado}) {
    const link = useRef(null);
    const liberado = useRef(false);
    const conferindo = useRef(false);
    const [erro, setErro] = useState(null);

    async function aoClicar(evento) {
        if (liberado.current) {
            liberado.current = false;
            return;
        }
        evento.preventDefault();
        if (conferindo.current) {
            return;
        }
        conferindo.current = true;
        setErro(null);
        try {
            const job = await consultarJob(jobId);
            if (!job.download_url) {
                onExpirado();
                return;
            }
            liberado.current = true;
            link.current.click();
        } catch (e) {
            setErro(mensagemDeErro(e));
        } finally {
            conferindo.current = false;
        }
    }

    return (
        <>
            <a ref={link} className="botao botao--primario" href={urlDownload(jobId)} download onClick={aoClicar}>
                Baixar resultado
            </a>
            {erro && (
                <p className="alerta alerta--erro" role="alert">
                    {erro}
                </p>
            )}
        </>
    );
}