process FAIRBIOHEADERS_VERIFY {
    tag "${meta.id}"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/fair-bioheaders:0.5.0--pyhdfd78af_0':
        'quay.io/biocontainers/fair-bioheaders:0.5.0--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(sequence)

    output:
    tuple val(meta), path("*.verify.txt"), emit: report
    tuple val("${task.process}"), val('fair-bioheaders'), eval("bioheaders --version"), emit: versions_fairbioheaders, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    // Single-quote for the shell: file names and meta.id may hold any character.
    def quote = { value -> "'" + value.toString().replace("'", "'\\''") + "'" }
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa'
        : sequence.name ==~ /.*\.gff3?(\.b?gz)?$/ ? 'gff3' : 'fasta'
    def report = quote.call("${prefix}.verify.txt")
    // A header that fails the schema or a checksum that does not match exits non-zero,
    // so the task fails; the report records the verified file and the result.
    """
    {
        printf 'file: %s\\n' ${quote.call(sequence)}
        bioheaders verify --type ${type} ${args} ${quote.call(sequence)}
    } > ${report}
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    def quote = { value -> "'" + value.toString().replace("'", "'\\''") + "'" }
    def report = quote.call("${prefix}.verify.txt")
    """
    touch ${report}
    """
}
