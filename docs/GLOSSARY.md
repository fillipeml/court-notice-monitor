# Glossary

Brazilian procedural terms that stay in Portuguese in this repository, and the API field names that are never renamed because they are the external contract.

## Terms

| Term | Meaning here |
|---|---|
| Domicílio Judicial Eletrônico | The electronic judicial domicile: the official inbox where courts deliver communications to companies. Operated on the PDPJ platform by the CNJ. |
| PDPJ | Plataforma Digital do Poder Judiciário, the national judiciary platform that hosts the domicile and its API. |
| CNJ | Conselho Nacional de Justiça, the National Council of Justice. Also names the unified case-number format `NNNNNNN-DD.AAAA.J.TR.OOOO`. |
| citação | Service of process: the communication that brings a party into a lawsuit. Automated flow. |
| notificação | Formal notice from a court. Automated flow. |
| intimação | Court notice to a party or lawyer that starts a procedural deadline. Human handling only. |
| vista, IPTA | Other communication types. Human handling only. |
| ciência | Acknowledgement: the act, with legal effect, of taking notice of a communication. Fetching the full text performs it. Never done here. |
| ciência tácita | Deemed acknowledgement after ten calendar days without reading. |
| prazo | Deadline. `dataFinalCiencia` is the deadline to acknowledge. |
| tenantId | The company's identifier inside the platform; required header for listing. |
| On-behalf-Of | Header carrying the responsible lawyer's CPF (individual tax id) for the audit trail. |
| CPF / CNPJ | Individual / company tax identifiers. The demo uses numbers that are invalid by construction. |

## API field names (kept as on the wire)

`numeroComunicacao`, `numeroProcesso`, `tipoComunicacao`, `status`, `dataComunicacao`, `dataFinalCiencia`, `tribunalOrigem`, `varaJudicial`, `urgente`, `autoresReclamantes`, `reus`, `nomeDestinatario`, `statusCiente`, `dataInicio`, `dataFim`, `perfis`, `tenantName`, `pessoa`, `empresaPrivada`, `orgaoPublico`, `razaoSocial`, `ativo`.

Status values: `EM_CURSO` (open), `INTEIRO_TEOR_OBTIDO` (full text fetched), `CIENTE` (acknowledged), `CIENCIA_AUTOMATICA` (deemed acknowledged), `CANCELADA` (cancelled).
