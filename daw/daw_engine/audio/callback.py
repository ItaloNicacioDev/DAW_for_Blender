"""
Audio Callback

Este arquivo é executado pela thread de áudio.

NUNCA importe bpy aqui.

Nunca faça prints.

Nunca faça acesso a disco.

Nunca carregue arquivos.

Nunca crie objetos.

Tudo precisa ser extremamente rápido.
"""

from __future__ import annotations

import numpy as np

from .state import ENGINE_STATE


class AudioCallback:

    def __init__(self):

        self.generator = None

    # -------------------------------------------------------

    def set_generator(self, generator):

        """
        Define quem irá gerar o áudio.

        Futuramente será o Mixer.
        """

        self.generator = generator

    # -------------------------------------------------------

    def __call__(

        self,

        outdata,

        frames,

        time,

        status,

    ):

        if status:

            ENGINE_STATE.xruns += 1

        if self.generator is None:

            outdata.fill(0)

            return

        audio = self.generator.process(frames)

        outdata[:] = audio

        ENGINE_STATE.frames_processed += frames