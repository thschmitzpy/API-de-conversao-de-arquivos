import {renderHook} from '@testing-library/react';
import useBloquearDrop from './useBloquearDrop';

function disparar(tipo, types) {
    const evento = new Event(tipo, {bubbles: true, cancelable: true});
    evento.dataTransfer = {types, dropEffect: 'copy'};
    document.body.dispatchEvent(evento);
    return evento;
}

test('arquivo solto fora da área não navega', () => {
    renderHook(() => useBloquearDrop());

    const arraste = disparar('dragover', ['Files']);
    expect(arraste.defaultPrevented).toBe(true);
    expect(arraste.dataTransfer.dropEffect).toBe('none');
    expect(disparar('drop', ['Files']).defaultPrevented).toBe(true);
});

test('não interfere no arraste que a área já tratou', () => {
    renderHook(() => useBloquearDrop());
    const tratar = (evento) => evento.preventDefault();
    document.body.addEventListener('dragover', tratar);

    expect(disparar('dragover', ['Files']).dataTransfer.dropEffect).toBe('copy');

    document.body.removeEventListener('dragover', tratar);
});

test('arrastar texto continua funcionando', () => {
    renderHook(() => useBloquearDrop());
    expect(disparar('drop', ['text/plain']).defaultPrevented).toBe(false);
});

test('para de bloquear ao desmontar', () => {
    const {unmount} = renderHook(() => useBloquearDrop());
    unmount();
    expect(disparar('drop', ['Files']).defaultPrevented).toBe(false);
});