process FAIRBIOHEADERS_VERIFY {
    tag "${meta.id}"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // Interim: the FAIR-bioHeaders image (built from the released wheel). Replace with the
    // Seqera/BioContainers URLs from `nf-core modules containers create` once
    // bioconda::fair-bioheaders is published.
    container "${workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container
        ? 'docker://ghcr.io/fair-bioheaders/fair-bioheaders:0.5.0'
        : 'ghcr.io/fair-bioheaders/fair-bioheaders:0.5.0'}"

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
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa' : 'fasta'
    // A header that fails the schema or a checksum that does not match exits non-zero,
    // so the task fails; the report records the verified file and the result.
    """
    {
        echo "file: ${sequence}"
        bioheaders verify --type ${type} ${args} '${sequence}'
    } > '${prefix}.verify.txt'
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch '${prefix}.verify.txt'
    """
}
