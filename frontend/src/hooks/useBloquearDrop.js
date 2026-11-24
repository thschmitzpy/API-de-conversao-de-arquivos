import {useEffect} from 'react';

export default function useBloquearDrop() {
    useEffect(() => {
        function bloquear(evento) {
            if (evento.defaultPrevented || !evento.dataTransfer?.types.includes('Files')) {
                return;
            }
            evento.preventDefault();
            evento.dataTransfer.dropEffect = 'none';
        }

        window.addEventListener('dragover', bloquear);
        window.addEventListener('drop', bloquear);
        return () => {
            window.removeEventListener('dragover', bloquear);
            window.removeEventListener('drop', bloquear);
        };
    }, []);
}