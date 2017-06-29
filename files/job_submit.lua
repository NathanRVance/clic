function slurm_job_submit(job_desc, part_list, submit_uid)
	if job_desc.partition == nil then
		local cpus = 1
		for power = 0,5 do
			if cpus >= job_desc.min_cpus then
				job_desc.partition = "clic-" .. cpus
				slurm.log_info("Assigning to partition: %s.", job_desc.partition)
				break
			end
			cpus = cpus * 2
		end
	end
	return slurm.SUCCESS
end

function slurm_job_modify(job_desc, job_rec, part_list, modify_uid)
	return slurm.SUCCESS
end

slurm.log_info("initialized")
return slurm.SUCCESS
